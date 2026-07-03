from src.backend.database import MORDatabase
from src.backend.forecast_models import ForecastTarget
from src.backend.row_identity import make_row_id


def test_input_loader_helpers_are_owned_by_forecast_workbench_inputs():
    from src.backend import forecast_workbench_inputs as inputs

    assert inputs.BudgetTarget.__module__ == "src.backend.forecast_workbench_inputs"
    assert inputs.load_adjustments.__module__ == "src.backend.forecast_workbench_inputs"
    assert inputs.load_budgets.__module__ == "src.backend.forecast_workbench_inputs"
    assert inputs.build_items_from_sales_data.__module__ == "src.backend.forecast_workbench_inputs"


def test_load_item_configs_treats_legacy_stop_label_as_discontinued(tmp_path):
    from src.backend.forecast_workbench_inputs import load_item_configs

    db = MORDatabase(tmp_path / "mor_workbench.db")
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO item_configs
            (product_code, item_status, status_label)
            VALUES ('P1', 'active', '停用')
            """
        )
        conn.commit()

    configs = load_item_configs(db)

    assert configs["P1"]["item_status"] == "discontinued"


def test_load_forecast_workbench_inputs_collects_db_sources(tmp_path):
    from src.backend.forecast_workbench_inputs import (
        ForecastWorkbenchInputs,
        load_forecast_workbench_inputs,
    )

    db = MORDatabase(tmp_path / "mor_workbench.db")
    row_id = make_row_id("Customer A", "P1")
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sales_records
            (order_date, customer_name, product_code, product_name, quantity, unit_price, amount)
            VALUES ('2026-04-10', 'Customer A', 'P1', 'Product One', 12, 10, 120)
            """
        )
        conn.execute(
            """
            INSERT INTO item_configs
            (product_code, is_excluded, is_budgeted, is_visible, price_quantity, item_status)
            VALUES ('P1', 1, 0, 0, 6, 'discontinued')
            """
        )
        conn.execute(
            """
            INSERT INTO forecast_adjustments
            (year, month, customer_name, product_code, manual_quantity, adjustment_reason)
            VALUES (2026, 5, 'Customer A', 'P1', 7, 'manual reason')
            """
        )
        conn.execute(
            """
            INSERT INTO budget_targets
            (year, month, customer_name, product_code, target_quantity, target_amount, base_target_quantity)
            VALUES (2026, 4, 'Customer A', 'P1', 40, 400, 4)
            """
        )
        conn.execute(
            """
            INSERT INTO budget_targets
            (year, month, customer_name, product_code, target_quantity, target_amount, base_target_quantity)
            VALUES (2026, 5, 'Customer A', 'P1', 50, 500, 5)
            """
        )
        conn.execute(
            """
            INSERT INTO daily_sales_actuals
            (sales_year, sales_month, sales_date, customer_name, product_code, product_name,
             actual_quantity, taxed_amount)
            VALUES (2026, 5, '2026-05-08', 'Customer A', 'P1', 'Product One', 3, 300)
            """
        )
        conn.commit()

    inputs = load_forecast_workbench_inputs(db, ForecastTarget(2026, 5))

    assert isinstance(inputs, ForecastWorkbenchInputs)
    assert len(inputs.data) == 1
    assert inputs.item_configs["P1"]["is_excluded"] is True
    assert inputs.excluded_item_ids == frozenset({"P1"})
    assert inputs.manual_adjustments[row_id] == 7
    assert inputs.adjustment_reasons[row_id] == "manual reason"
    assert inputs.budget_targets[row_id].target_quantity == 50
    assert inputs.budget_year_map[row_id][3] == 40
    assert inputs.budget_year_map[row_id][4] == 50
    assert inputs.budget_year_amount_map[row_id][3] == 400
    assert inputs.budget_year_amount_map[row_id][4] == 500
    assert inputs.budget_months == [(2026, 4), (2026, 5)]
    assert inputs.daily_actuals[row_id].actual_quantity == 3


def test_workbench_inputs_exposes_row_month_interface_without_losing_company_budget(tmp_path):
    from src.backend.forecast_workbench_inputs import (
        BudgetTarget,
        load_forecast_workbench_inputs,
    )

    db = MORDatabase(tmp_path / "mor_workbench.db")
    row_id = make_row_id("Customer A", "P1")
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sales_records
            (order_date, customer_name, product_code, product_name, quantity, unit_price, amount)
            VALUES ('2026-04-10', 'Customer A', 'P1', 'Product One', 12, 10, 120)
            """
        )
        conn.execute(
            """
            INSERT INTO item_configs
            (product_code, is_excluded, is_budgeted, is_visible, price_quantity, item_status)
            VALUES ('P1', 1, 0, 0, 6, 'discontinued')
            """
        )
        conn.execute(
            """
            INSERT INTO forecast_adjustments
            (year, month, customer_name, product_code, manual_quantity, adjustment_reason)
            VALUES (2026, 5, 'Customer A', 'P1', 7, 'manual reason')
            """
        )
        conn.execute(
            """
            INSERT INTO budget_targets
            (year, month, customer_name, product_code, target_quantity, target_amount, base_target_quantity)
            VALUES (2026, 5, 'Customer A', 'P1', 50, 500, 5)
            """
        )
        conn.execute(
            """
            INSERT INTO daily_sales_actuals
            (sales_year, sales_month, sales_date, customer_name, product_code, product_name,
             actual_quantity, taxed_amount)
            VALUES (2026, 5, '2026-05-08', 'Customer A', 'P1', 'Product One', 3, 300)
            """
        )
        conn.commit()

    inputs = load_forecast_workbench_inputs(db, ForecastTarget(2026, 5))
    row_input = inputs.row_month_input(row_id, "P1")

    assert row_input.manual_adjustment == 7
    assert row_input.adjustment_reason == "manual reason"
    assert row_input.current_budget == BudgetTarget(0.0, 0.0)
    assert row_input.budget_monthly == [0.0] * 12
    assert row_input.budget_monthly_amount == [0.0] * 12
    assert row_input.price_quantity == 6
    assert row_input.item_status == "discontinued"
    assert row_input.is_budgeted is False
    assert row_input.is_visible is False
    assert inputs.visible_product("P1") is False
    assert inputs.forecast_excluded_product_ids == frozenset({"P1"})
    assert inputs.company_budgets == [BudgetTarget(50, 500, 5)]
    assert inputs.available_budget_months == [(2026, 5)]
    assert inputs.daily_actuals[row_id].actual_quantity == 3
