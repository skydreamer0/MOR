from src.backend.row_identity import ForecastRowIdentity, make_row_id, parse_row_id


def test_make_and_parse_row_id_preserves_legacy_customer_product_contract():
    row_id = make_row_id("Hospital A", "P1")

    assert row_id == "Hospital A__P1"
    assert parse_row_id(row_id) == ForecastRowIdentity(
        customer_name="Hospital A",
        product_code="P1",
    )


def test_parse_row_id_preserves_legacy_missing_product_fallback():
    assert parse_row_id("Hospital A") == ForecastRowIdentity(
        customer_name="Hospital A",
        product_code="",
    )


def test_make_row_id_uses_encoded_form_when_values_contain_legacy_delimiter():
    row_id = make_row_id("Hospital__A", "P1")

    assert row_id != "Hospital__A__P1"
    assert parse_row_id(row_id) == ForecastRowIdentity(
        customer_name="Hospital__A",
        product_code="P1",
    )


def test_make_row_id_distinguishes_delimiter_collision_pairs():
    first = make_row_id("A__B", "C")
    second = make_row_id("A", "B__C")

    assert first != second
    assert parse_row_id(first) == ForecastRowIdentity(customer_name="A__B", product_code="C")
    assert parse_row_id(second) == ForecastRowIdentity(customer_name="A", product_code="B__C")
