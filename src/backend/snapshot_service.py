"""Snapshot Service — save, list, and lock forecast versions.

Provides business logic for the forecast versioning system:
- Save a snapshot (Draft / Final)
- List snapshots for a given month
- Check if a month is finalized (locked)
- Load a snapshot's row data for read-only review
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from src.backend.database import MORDatabase
from src.backend.forecast_models import ForecastRow


@dataclass(frozen=True)
class SnapshotMeta:
    """Metadata for a saved forecast snapshot."""
    id: int
    snapshot_name: str
    snapshot_type: str  # 'Draft' or 'Final'
    year: int
    month: int
    created_by: str
    created_at: str
    row_count: int


@dataclass(frozen=True)
class SnapshotItem:
    """A single row within a snapshot."""
    customer_name: str
    product_code: str
    system_forecast: float
    manual_adjustment: Optional[float]
    final_forecast: float


def serialize_forecast_rows_for_snapshot(rows: Iterable[ForecastRow]) -> list[dict]:
    """Convert forecast rows into snapshot row dictionaries."""
    return [
        {
            "customer_name": row.customer,
            "product_code": row.product_code,
            "system_forecast": row.system_forecast,
            "manual_adjustment": row.manual_adjustment,
            "final_forecast": row.final_forecast,
            "product_name": row.product_name,
            "base_forecast": row.system_forecast,
            "current_forecast": row.final_forecast,
            "adjustment_reason": row.adjustment_reason,
        }
        for row in rows
    ]


def save_snapshot(
    db: MORDatabase,
    year: int,
    month: int,
    snapshot_name: str,
    snapshot_type: str,
    rows: list[dict],
    created_by: str = "User",
) -> int:
    """Persist a snapshot of the current forecast state.

    Args:
        rows: list of dicts with keys:
            customer_name, product_code, system_forecast,
            manual_adjustment, final_forecast

    Returns:
        The new snapshot ID.

    Raises:
        ValueError: if the month is already finalized.
    """
    if snapshot_type == "Final" and is_finalized(db, year, month):
        raise ValueError(f"{year}/{month:02d} 已定稿，無法重複定稿。")
    if snapshot_type == "CloseMonth" and _has_snapshot_type(db, year, month, "CloseMonth"):
        raise ValueError(f"{year}/{month:02d} 已關帳，無法重複關帳。")

    with db.get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO forecast_snapshots
            (snapshot_name, snapshot_type, year, month, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (snapshot_name, snapshot_type, year, month, created_by))
        snapshot_id = cursor.lastrowid

        for row in rows:
            conn.execute("""
                INSERT INTO snapshot_items
                (snapshot_id, customer_name, product_code,
                 system_forecast, manual_adjustment, final_forecast)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id,
                row["customer_name"],
                row["product_code"],
                row.get("system_forecast", 0),
                row.get("manual_adjustment"),
                row.get("final_forecast", 0),
            ))
        conn.commit()

    return snapshot_id


def list_snapshots(
    db: MORDatabase,
    year: int,
    month: int,
) -> list[SnapshotMeta]:
    """Return all snapshots for a given year/month, newest first."""
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT s.id, s.snapshot_name, s.snapshot_type,
                   s.year, s.month, s.created_by, s.created_at,
                   COUNT(i.id) AS row_count
            FROM forecast_snapshots s
            LEFT JOIN snapshot_items i ON i.snapshot_id = s.id
            WHERE s.year = ? AND s.month = ?
            GROUP BY s.id
            ORDER BY s.id DESC
        """, (year, month)).fetchall()

    return [
        SnapshotMeta(
            id=r["id"],
            snapshot_name=r["snapshot_name"],
            snapshot_type=r["snapshot_type"],
            year=r["year"],
            month=r["month"],
            created_by=r["created_by"],
            created_at=r["created_at"],
            row_count=r["row_count"],
        )
        for r in rows
    ]


def load_snapshot_items(
    db: MORDatabase,
    snapshot_id: int,
) -> list[SnapshotItem]:
    """Load all row-level data for a specific snapshot."""
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT customer_name, product_code,
                   system_forecast, manual_adjustment, final_forecast
            FROM snapshot_items
            WHERE snapshot_id = ?
        """, (snapshot_id,)).fetchall()

    return [
        SnapshotItem(
            customer_name=r["customer_name"],
            product_code=r["product_code"],
            system_forecast=float(r["system_forecast"] or 0),
            manual_adjustment=float(r["manual_adjustment"]) if r["manual_adjustment"] is not None else None,
            final_forecast=float(r["final_forecast"] or 0),
        )
        for r in rows
    ]


def is_finalized(db: MORDatabase, year: int, month: int) -> bool:
    """Check whether a month has been marked as Final."""
    return _has_snapshot_type(db, year, month, "Final")


def _has_snapshot_type(db: MORDatabase, year: int, month: int, snapshot_type: str) -> bool:
    """Check whether a month already has a snapshot of the given type."""
    with db.get_connection() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM forecast_snapshots
            WHERE year = ? AND month = ? AND snapshot_type = ?
        """, (year, month, snapshot_type)).fetchone()
    return row["cnt"] > 0


def delete_snapshot(db: MORDatabase, snapshot_id: int) -> None:
    """Delete a snapshot and its items. Only drafts should be deletable."""
    with db.get_connection() as conn:
        # Safety: prevent deleting finalized snapshots
        meta = conn.execute(
            "SELECT snapshot_type FROM forecast_snapshots WHERE id = ?",
            (snapshot_id,)
        ).fetchone()
        if meta and meta["snapshot_type"] in {"Final", "CloseMonth"}:
            raise ValueError("無法刪除已定稿的快照。")

        conn.execute("DELETE FROM snapshot_items WHERE snapshot_id = ?", (snapshot_id,))
        conn.execute("DELETE FROM forecast_snapshots WHERE id = ?", (snapshot_id,))
        conn.commit()
