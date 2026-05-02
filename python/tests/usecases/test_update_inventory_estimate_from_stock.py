from usecases.update_inventory_estimate_from_stock import _parse_stock_quantity


def test_parse_stock_quantity_plain_integer():
    assert _parse_stock_quantity("4047") == 4047


def test_parse_stock_quantity_with_thousands_separator():
    assert _parse_stock_quantity("4,047") == 4047


def test_parse_stock_quantity_zero():
    assert _parse_stock_quantity("0") == 0


def test_parse_stock_quantity_empty_string():
    assert _parse_stock_quantity("") == 0


def test_parse_stock_quantity_whitespace():
    assert _parse_stock_quantity("  1,234  ") == 1234


def test_parse_stock_quantity_non_numeric():
    assert _parse_stock_quantity("abc") == 0


def test_parse_stock_quantity_none():
    assert _parse_stock_quantity(None) == 0


def test_parse_stock_quantity_int_value():
    assert _parse_stock_quantity(123) == 123
