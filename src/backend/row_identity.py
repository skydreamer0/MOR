from __future__ import annotations

import base64
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ForecastRowIdentity:
    customer_name: str
    product_code: str


def make_row_id(customer_name: object, product_code: object) -> str:
    customer = str(customer_name)
    product = str(product_code)
    if "__" not in customer and "__" not in product:
        return f"{customer}__{product}"

    payload = json.dumps([customer, product], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"rowid:v1:{encoded}"


def parse_row_id(row_id: str) -> ForecastRowIdentity:
    if row_id.startswith("rowid:v1:"):
        encoded = row_id.removeprefix("rowid:v1:")
        padded = encoded + ("=" * (-len(encoded) % 4))
        customer_name, product_code = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        return ForecastRowIdentity(customer_name=customer_name, product_code=product_code)

    customer_name, separator, product_code = row_id.partition("__")
    if not separator:
        return ForecastRowIdentity(customer_name=row_id, product_code="")
    return ForecastRowIdentity(customer_name=customer_name, product_code=product_code)
