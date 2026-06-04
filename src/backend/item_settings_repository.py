from __future__ import annotations

from src.backend.data_loader import normalize_product_code


def update_item_configs(db, items: list[dict]) -> None:
    """Upsert item config rows from normalized item setting payloads."""
    with db.get_connection() as conn:
        for item in items:
            pid = normalize_product_code(item["product_code"])
            is_excluded = int(bool(item.get("is_excluded", False)))
            is_budgeted = int(bool(item.get("is_budgeted", True)))
            is_visible = int(bool(item.get("is_visible", True)))
            price_quantity = int(item.get("price_quantity", 0))
            item_status = item.get("item_status", "active")
            if item_status not in {"active", "discontinued"}:
                item_status = "active"
            conn.execute(
                """
                INSERT OR IGNORE INTO item_configs
                (product_code, is_excluded, is_budgeted, is_visible,
                 price_quantity, item_status, status_label, custom_category)
                VALUES (?, 0, 1, 1, 0, 'active', NULL, NULL)
                """,
                (pid,),
            )
            conn.execute(
                """
                UPDATE item_configs
                SET is_excluded = ?, is_budgeted = ?, is_visible = ?,
                    price_quantity = ?, item_status = ?
                WHERE product_code = ?
                """,
                (is_excluded, is_budgeted, is_visible, price_quantity, item_status, pid),
            )
        conn.commit()
