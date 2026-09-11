from __future__ import annotations

from domain.inventory.value_objects.stock_shortfall import StockShortfall, collect_shortfalls


def test_reports_the_quantity_that_no_row_could_absorb() -> None:
    shortfall = StockShortfall(asin="B001", fba_quantity=1000, assigned_quantity=700)

    assert shortfall.quantity == 300


def test_collects_asins_whose_stock_exceeds_the_rows() -> None:
    result = collect_shortfalls({"B001": 1000, "B002": 500}, {"B001": 700, "B002": 500})

    assert result == [StockShortfall(asin="B001", fba_quantity=1000, assigned_quantity=700)]


def test_collects_asins_that_have_no_row_at_all() -> None:
    result = collect_shortfalls({"B001": 40}, {})

    assert result == [StockShortfall(asin="B001", fba_quantity=40, assigned_quantity=0)]


def test_ignores_asins_without_stock() -> None:
    assert collect_shortfalls({"B001": 0}, {}) == []


def test_orders_by_quantity_so_the_worst_comes_first() -> None:
    result = collect_shortfalls({"B001": 100, "B002": 900}, {"B001": 0, "B002": 0})

    assert [s.asin for s in result] == ["B002", "B001"]
