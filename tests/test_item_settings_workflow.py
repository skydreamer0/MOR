from werkzeug.datastructures import MultiDict

from src.backend.item_settings_workflow import build_item_config_payloads_from_form


def test_build_item_config_payloads_from_form_preserves_item_settings_payload_shape():
    form = MultiDict(
        [
            ("product_codes", "101.0"),
            ("product_codes", "P2"),
            ("is_excluded_101", "1"),
            ("is_budgeted_101", "1"),
            ("is_visible_101", "1"),
            ("price_quantity_101", "24.7"),
            ("item_status_101", "discontinued"),
            ("price_quantity_P2", "not-a-number"),
            ("item_status_P2", "retired"),
        ]
    )

    items = build_item_config_payloads_from_form(form)

    assert items == [
        {
            "product_code": "101",
            "is_excluded": True,
            "is_budgeted": True,
            "is_visible": True,
            "price_quantity": 24,
            "item_status": "discontinued",
        },
        {
            "product_code": "P2",
            "is_excluded": False,
            "is_budgeted": False,
            "is_visible": False,
            "price_quantity": 0,
            "item_status": "active",
        },
    ]
