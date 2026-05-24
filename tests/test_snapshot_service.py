"""Tests for snapshot_service — save, list, finalize, delete."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.backend.database import MORDatabase
from src.backend.forecast_models import ForecastRow
from src.backend.snapshot_service import (
    delete_snapshot,
    is_finalized,
    list_snapshots,
    load_snapshot_items,
    save_snapshot,
    serialize_forecast_rows_for_snapshot,
)


@pytest.fixture
def db(tmp_path: Path):
    return MORDatabase(tmp_path / "test.db")


def _sample_rows():
    return [
        {
            "customer_name": "A醫院",
            "product_code": "P001",
            "system_forecast": 10.0,
            "manual_adjustment": 12.0,
            "final_forecast": 12.0,
        },
        {
            "customer_name": "B醫院",
            "product_code": "P002",
            "system_forecast": 5.0,
            "manual_adjustment": None,
            "final_forecast": 5.0,
        },
    ]


def _forecast_row() -> ForecastRow:
    return ForecastRow(
        row_id="A__P001",
        customer="A客戶",
        product_code="P001",
        product_name="測試品",
        latest_order_date=date(2026, 4, 10),
        cycle_days=30,
        next_order_date=date(2026, 5, 10),
        auto_in_month=True,
        last_year_same_month_qty=8.0,
        this_year_same_month_qty=9.0,
        latest_price=100.0,
        system_forecast=10.0,
        manual_adjustment=12.0,
        final_forecast=12.0,
        estimated_amount=1200.0,
        forecast_basis="cycle",
        adjustment_reason="customer confirmed",
    )


def test_serialize_forecast_rows_for_snapshot_preserves_snapshot_row_contract():
    rows = serialize_forecast_rows_for_snapshot([_forecast_row()])

    assert rows == [
        {
            "customer_name": "A客戶",
            "product_code": "P001",
            "system_forecast": 10.0,
            "manual_adjustment": 12.0,
            "final_forecast": 12.0,
            "product_name": "測試品",
            "base_forecast": 10.0,
            "current_forecast": 12.0,
            "adjustment_reason": "customer confirmed",
        }
    ]


class TestSaveSnapshot:
    def test_saves_draft(self, db):
        sid = save_snapshot(db, 2026, 5, "草稿 v1", "Draft", _sample_rows())
        assert sid is not None
        assert sid > 0

    def test_saves_final(self, db):
        sid = save_snapshot(db, 2026, 5, "定稿", "Final", _sample_rows())
        assert sid > 0

    def test_prevents_double_final(self, db):
        save_snapshot(db, 2026, 5, "定稿 1", "Final", _sample_rows())
        with pytest.raises(ValueError, match="已定稿"):
            save_snapshot(db, 2026, 5, "定稿 2", "Final", _sample_rows())


class TestListSnapshots:
    def test_empty(self, db):
        assert list_snapshots(db, 2026, 5) == []

    def test_returns_newest_first(self, db):
        save_snapshot(db, 2026, 5, "First", "Draft", _sample_rows())
        save_snapshot(db, 2026, 5, "Second", "Draft", _sample_rows())
        snaps = list_snapshots(db, 2026, 5)
        assert len(snaps) == 2
        assert snaps[0].snapshot_name == "Second"
        assert snaps[1].snapshot_name == "First"

    def test_includes_row_count(self, db):
        save_snapshot(db, 2026, 5, "Test", "Draft", _sample_rows())
        snaps = list_snapshots(db, 2026, 5)
        assert snaps[0].row_count == 2


class TestLoadSnapshotItems:
    def test_loads_items(self, db):
        sid = save_snapshot(db, 2026, 5, "Test", "Draft", _sample_rows())
        items = load_snapshot_items(db, sid)
        assert len(items) == 2
        assert items[0].customer_name == "A醫院"
        assert items[0].manual_adjustment == 12.0
        assert items[1].manual_adjustment is None


class TestIsFinalized:
    def test_not_finalized(self, db):
        assert is_finalized(db, 2026, 5) is False

    def test_finalized(self, db):
        save_snapshot(db, 2026, 5, "定稿", "Final", _sample_rows())
        assert is_finalized(db, 2026, 5) is True

    def test_draft_does_not_count(self, db):
        save_snapshot(db, 2026, 5, "草稿", "Draft", _sample_rows())
        assert is_finalized(db, 2026, 5) is False


class TestDeleteSnapshot:
    def test_deletes_draft(self, db):
        sid = save_snapshot(db, 2026, 5, "草稿", "Draft", _sample_rows())
        delete_snapshot(db, sid)
        assert list_snapshots(db, 2026, 5) == []

    def test_prevents_deleting_final(self, db):
        sid = save_snapshot(db, 2026, 5, "定稿", "Final", _sample_rows())
        with pytest.raises(ValueError, match="無法刪除"):
            delete_snapshot(db, sid)
