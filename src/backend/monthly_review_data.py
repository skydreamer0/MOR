from __future__ import annotations

from dataclasses import dataclass

from src.backend.database import MORDatabase
from src.backend.row_identity import make_row_id


@dataclass(frozen=True)
class MonthlyReviewDataReader:
    db: MORDatabase

    def close_record(self, year: int, month: int) -> dict | None:
        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT year, month, closed_at, final_snapshot_id,
                       actual_quantity_total, actual_amount_total
                FROM   month_close_records
                WHERE  year = ? AND month = ?
                """,
                (year, month),
            ).fetchone()
        return dict(row) if row else None

    def reviewable_months(self) -> list[tuple[int, int]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT year, month
                FROM   month_close_records
                WHERE  final_snapshot_id IS NOT NULL
                ORDER  BY year DESC, month DESC
                """
            ).fetchall()
        return [(row["year"], row["month"]) for row in rows]

    def closed_months_with_snapshots_ending(
        self,
        year: int,
        month: int,
        count: int,
    ) -> list[tuple[int, int]]:
        candidates: list[tuple[int, int]] = []
        y, m = year, month
        for _ in range(count):
            candidates.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        candidates.reverse()

        with self.db.get_connection() as conn:
            result = []
            for y, m in candidates:
                row = conn.execute(
                    """
                    SELECT id
                    FROM   month_close_records
                    WHERE  year = ? AND month = ? AND final_snapshot_id IS NOT NULL
                    """,
                    (y, m),
                ).fetchone()
                if row:
                    result.append((y, m))
        return result

    def customer_amounts(self, year: int, month: int) -> dict[str, float]:
        with self.db.get_connection() as conn:
            if self._is_closed_in_connection(conn, year, month):
                rows = conn.execute(
                    """
                    SELECT customer_name, SUM(taxed_amount) AS amt
                    FROM   daily_sales_actuals
                    WHERE  sales_year = ? AND sales_month = ?
                    GROUP  BY customer_name
                    """,
                    (year, month),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT customer_name, SUM(amount) AS amt
                    FROM   sales_records
                    WHERE  strftime('%Y', order_date) = ?
                      AND  strftime('%m', order_date) = ?
                    GROUP  BY customer_name
                    """,
                    (str(year), f"{month:02d}"),
                ).fetchall()
        return {row["customer_name"]: float(row["amt"] or 0) for row in rows if row["customer_name"]}

    def product_totals(
        self,
        year: int,
        month: int,
    ) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
        amounts: dict[str, float] = {}
        quantities: dict[str, float] = {}
        names: dict[str, str] = {}
        with self.db.get_connection() as conn:
            if self._is_closed_in_connection(conn, year, month):
                rows = conn.execute(
                    """
                    SELECT product_code,
                           MAX(product_name)    AS name,
                           SUM(actual_quantity) AS qty,
                           SUM(taxed_amount)    AS amt
                    FROM   daily_sales_actuals
                    WHERE  sales_year = ? AND sales_month = ?
                    GROUP  BY product_code
                    """,
                    (year, month),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT product_code,
                           MAX(product_name) AS name,
                           SUM(quantity)     AS qty,
                           SUM(amount)       AS amt
                    FROM   sales_records
                    WHERE  strftime('%Y', order_date) = ?
                      AND  strftime('%m', order_date) = ?
                    GROUP  BY product_code
                    """,
                    (str(year), f"{month:02d}"),
                ).fetchall()
        for row in rows:
            code = row["product_code"]
            if not code:
                continue
            amounts[code] = float(row["amt"] or 0)
            quantities[code] = float(row["qty"] or 0)
            if row["name"]:
                names[code] = row["name"]
        return amounts, quantities, names

    def budget_rows(self, year: int, month: int) -> dict[str, dict]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT customer_name, product_code,
                       target_quantity, target_amount, base_target_quantity
                FROM   budget_targets
                WHERE  year = ? AND month = ?
                """,
                (year, month),
            ).fetchall()
        return {
            make_row_id(row["customer_name"], row["product_code"]): {
                "target_quantity": float(row["target_quantity"] or 0),
                "target_amount": float(row["target_amount"] or 0),
                "base_target_quantity": float(row["base_target_quantity"] or 0),
            }
            for row in rows
        }

    def budget_amounts_by_customer(self, year: int, month: int) -> dict[str, float]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT customer_name, SUM(target_amount) AS amt
                FROM   budget_targets
                WHERE  year = ? AND month = ?
                GROUP  BY customer_name
                """,
                (year, month),
            ).fetchall()
        return {row["customer_name"]: float(row["amt"] or 0) for row in rows if row["customer_name"]}

    def product_names(self) -> dict[str, str]:
        name_map: dict[str, str] = {}
        with self.db.get_connection() as conn:
            for sql in (
                "SELECT product_code, MAX(product_name) AS n FROM daily_sales_actuals "
                "WHERE product_name IS NOT NULL AND product_name != '' GROUP BY product_code",
                "SELECT product_code, MAX(product_name) AS n FROM sales_records "
                "WHERE product_name IS NOT NULL AND product_name != '' GROUP BY product_code",
                "SELECT product_code, MAX(product_name) AS n FROM current_month_records "
                "WHERE product_name IS NOT NULL AND product_name != '' GROUP BY product_code",
            ):
                for row in conn.execute(sql).fetchall():
                    code = row["product_code"]
                    if code and code not in name_map and row["n"]:
                        name_map[code] = row["n"]
        return name_map

    def price_quantities(self) -> dict[str, float]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT product_code, price_quantity
                FROM   item_configs
                WHERE  price_quantity > 0
                """
            ).fetchall()
        return {
            row["product_code"]: float(row["price_quantity"] or 0)
            for row in rows
            if row["product_code"]
        }

    def quantity_multiplier(self, product_code: str) -> float:
        return quantity_multiplier(product_code, self.price_quantities())

    def snapshot_forecasts(self, year: int, month: int) -> dict[str, dict]:
        close_record = self.close_record(year, month)
        snapshot_id = close_record["final_snapshot_id"] if close_record else None
        return self.snapshot_forecasts_by_id(snapshot_id)

    def snapshot_forecasts_by_id(self, snapshot_id: int | None) -> dict[str, dict]:
        if snapshot_id is None:
            return {}
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT customer_name, product_code, final_forecast
                FROM   snapshot_items
                WHERE  snapshot_id = ?
                """,
                (snapshot_id,),
            ).fetchall()
        return {
            make_row_id(row["customer_name"], row["product_code"]): {
                "final_forecast": float(row["final_forecast"] or 0),
            }
            for row in rows
        }

    def actuals_by_row(self, year: int, month: int) -> dict[str, dict]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT customer_name, product_code,
                       MAX(product_name)    AS product_name,
                       SUM(actual_quantity) AS qty,
                       SUM(taxed_amount)    AS amount
                FROM   daily_sales_actuals
                WHERE  sales_year = ? AND sales_month = ?
                GROUP  BY customer_name, product_code
                """,
                (year, month),
            ).fetchall()
        return {
            make_row_id(row["customer_name"], row["product_code"]): {
                "customer_name": row["customer_name"],
                "product_code": row["product_code"],
                "product_name": row["product_name"] or "",
                "qty": float(row["qty"] or 0),
                "amount": float(row["amount"] or 0),
            }
            for row in rows
        }

    def actual_amounts_by_pair(self, year: int, month: int) -> dict[tuple[str, str], float]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT customer_name, product_code, SUM(taxed_amount) AS amt
                FROM   daily_sales_actuals
                WHERE  sales_year = ? AND sales_month = ?
                GROUP  BY customer_name, product_code
                """,
                (year, month),
            ).fetchall()
        return {
            (row["customer_name"], row["product_code"]): float(row["amt"] or 0)
            for row in rows
        }

    def names_for_month(self, year: int, month: int) -> dict[tuple[str, str], str]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT customer_name, product_code, MAX(product_name) AS name
                FROM   daily_sales_actuals
                WHERE  sales_year = ? AND sales_month = ?
                GROUP  BY customer_name, product_code
                """,
                (year, month),
            ).fetchall()
        return {
            (row["customer_name"], row["product_code"]): (row["name"] or "")
            for row in rows
        }

    def last_year_rows(
        self,
        year: int,
        month: int,
        price_quantities: dict[str, float] | None = None,
    ) -> dict[str, dict]:
        ly_year = year - 1
        price_quantities = price_quantities or {}
        with self.db.get_connection() as conn:
            closed = self._is_closed_in_connection(conn, ly_year, month)
            if closed:
                rows = conn.execute(
                    """
                    SELECT customer_name, product_code,
                           SUM(actual_quantity) AS qty,
                           SUM(taxed_amount)    AS amount
                    FROM   daily_sales_actuals
                    WHERE  sales_year = ? AND sales_month = ?
                    GROUP  BY customer_name, product_code
                    """,
                    (ly_year, month),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT customer_name, product_code,
                           SUM(quantity) AS qty,
                           SUM(amount)   AS amount
                    FROM   sales_records
                    WHERE  strftime('%Y', order_date) = ?
                      AND  strftime('%m', order_date) = ?
                    GROUP  BY customer_name, product_code
                    """,
                    (str(ly_year), f"{month:02d}"),
                ).fetchall()
        result = {}
        for row in rows:
            product_code = row["product_code"]
            qty = float(row["qty"] or 0)
            if closed:
                qty *= quantity_multiplier(product_code, price_quantities)
            result[make_row_id(row["customer_name"], product_code)] = {
                "qty": qty,
                "amount": float(row["amount"] or 0),
            }
        return result

    def fallback_unit_prices(
        self,
        year: int,
        month: int,
        price_quantities: dict[str, float] | None = None,
    ) -> dict[str, float]:
        prices: dict[str, float] = {}
        price_quantities = price_quantities or {}
        period_start = f"{year}-{month:02d}-01"
        with self.db.get_connection() as conn:
            for row in conn.execute(
                """
                SELECT customer_name, product_code,
                       SUM(taxed_amount)    AS amt,
                       SUM(actual_quantity) AS qty
                FROM   daily_sales_actuals
                WHERE  sales_date < ?
                GROUP  BY customer_name, product_code
                """,
                (period_start,),
            ).fetchall():
                qty = float(row["qty"] or 0) * quantity_multiplier(row["product_code"], price_quantities)
                amount = float(row["amt"] or 0)
                if qty > 0 and amount > 0:
                    prices[make_row_id(row["customer_name"], row["product_code"])] = amount / qty
            for row in conn.execute(
                """
                SELECT customer_name, product_code,
                       SUM(quantity) AS qty,
                       SUM(amount)   AS amt
                FROM   sales_records
                WHERE  order_date < ?
                GROUP  BY customer_name, product_code
                """,
                (period_start,),
            ).fetchall():
                row_id = make_row_id(row["customer_name"], row["product_code"])
                if row_id in prices:
                    continue
                qty = float(row["qty"] or 0)
                amount = float(row["amt"] or 0)
                if qty > 0 and amount > 0:
                    prices[row_id] = amount / qty
        return prices

    def forecast_amounts(
        self,
        year: int,
        month: int,
        *,
        historical_fallback: bool = False,
    ) -> dict[tuple[str, str], float]:
        forecasts = self.snapshot_forecasts(year, month)
        if not forecasts:
            return {}

        price_quantities = self.price_quantities()
        period_prices = self._period_unit_prices(year, month, price_quantities)
        fallback_prices = (
            self.fallback_unit_prices(year, month, price_quantities)
            if historical_fallback
            else {}
        )
        amounts: dict[tuple[str, str], float] = {}
        for row_id, forecast in forecasts.items():
            customer_name, product_code = _parse_row_id_tuple(row_id)
            qty = float(forecast["final_forecast"] or 0)
            unit_price = period_prices.get(row_id, 0.0) or fallback_prices.get(row_id, 0.0)
            if qty > 0 and unit_price > 0:
                amounts[(customer_name, product_code)] = qty * unit_price
        return amounts

    def _period_unit_prices(
        self,
        year: int,
        month: int,
        price_quantities: dict[str, float],
    ) -> dict[str, float]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT customer_name, product_code,
                       SUM(actual_quantity) AS qty,
                       SUM(taxed_amount)    AS amt
                FROM   daily_sales_actuals
                WHERE  sales_year = ? AND sales_month = ?
                GROUP  BY customer_name, product_code
                """,
                (year, month),
            ).fetchall()
        result: dict[str, float] = {}
        for row in rows:
            qty = float(row["qty"] or 0) * quantity_multiplier(row["product_code"], price_quantities)
            amount = float(row["amt"] or 0)
            if qty > 0 and amount > 0:
                result[make_row_id(row["customer_name"], row["product_code"])] = amount / qty
        return result

    @staticmethod
    def _is_closed_in_connection(conn, year: int, month: int) -> bool:
        row = conn.execute(
            "SELECT id FROM month_close_records WHERE year = ? AND month = ?",
            (year, month),
        ).fetchone()
        return row is not None


def quantity_multiplier(product_code: str, price_quantities: dict[str, float]) -> float:
    multiplier = price_quantities.get(product_code, 0.0)
    return multiplier if multiplier > 0 else 1.0


def _parse_row_id_tuple(row_id: str) -> tuple[str, str]:
    from src.backend.row_identity import parse_row_id

    identity = parse_row_id(row_id)
    return identity.customer_name, identity.product_code
