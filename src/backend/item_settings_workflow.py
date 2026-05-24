from __future__ import annotations

from typing import Any

from src.backend.data_loader import normalize_product_code


_VALID_ITEM_STATUSES = {"active", "discontinued"}


def build_item_config_payloads_from_form(form: Any) -> list[dict]:
    items = []
    for raw_product_code in form.getlist("product_codes"):
        product_code = normalize_product_code(raw_product_code)
        try:
            price_quantity = int(float(form.get(f"price_quantity_{product_code}") or 0))
        except ValueError:
            price_quantity = 0
        item_status = form.get(f"item_status_{product_code}", "active")
        if item_status not in _VALID_ITEM_STATUSES:
            item_status = "active"
        items.append(
            {
                "product_code": product_code,
                "is_excluded": form.get(f"is_excluded_{product_code}") == "1",
                "is_budgeted": form.get(f"is_budgeted_{product_code}") == "1",
                "is_visible": form.get(f"is_visible_{product_code}") == "1",
                "price_quantity": price_quantity,
                "item_status": item_status,
            }
        )
    return items


parse_item_settings_form = build_item_config_payloads_from_form
