from __future__ import annotations

from usecases.delete_blank_rows import _build_delete_requests, _is_blank_row

HEADERS = ["購入日", "商品名", "ASIN", "SKU", "状態", "購入数", "備考"]


def _row(**values: str) -> list[str]:
    return [values.get(h, "") for h in HEADERS]


def test_状態数式だけ残った行は空白行() -> None:
    assert _is_blank_row(HEADERS, _row(状態="未発送")) is True


def test_全列空の行は空白行() -> None:
    assert _is_blank_row(HEADERS, _row()) is True


def test_空白文字だけの行は空白行() -> None:
    assert _is_blank_row(HEADERS, _row(商品名="   ", 状態="未発送")) is True


def test_ヘッダーより短い行も空白行として扱える() -> None:
    assert _is_blank_row(HEADERS, ["", "", ""]) is True


def test_商品名があれば空白行ではない() -> None:
    assert _is_blank_row(HEADERS, _row(商品名="テスト商品", 状態="未発送")) is False


def test_購入数だけでも空白行ではない() -> None:
    assert _is_blank_row(HEADERS, _row(購入数="100", 状態="未発送")) is False


def test_備考だけでも空白行ではない() -> None:
    assert _is_blank_row(HEADERS, _row(備考="次回持ち越し", 状態="未発送")) is False


def test_ヘッダー範囲外の余剰セルに値があれば空白行ではない() -> None:
    assert _is_blank_row(HEADERS, _row(状態="未発送") + ["残骸"]) is False


def test_在庫ありでも実データが空なら空白行() -> None:
    # 状態は数式なので値が何であれ判定に使わない
    assert _is_blank_row(HEADERS, _row(状態="在庫あり")) is True


def test_削除リクエストは行番号の降順() -> None:
    requests = _build_delete_requests(sheet_id=123, row_numbers=[14, 39, 104])
    starts = [r["deleteDimension"]["range"]["startIndex"] for r in requests]
    assert starts == [103, 38, 13]


def test_削除リクエストは1行ずつの範囲になる() -> None:
    requests = _build_delete_requests(sheet_id=7, row_numbers=[57])
    rng = requests[0]["deleteDimension"]["range"]
    assert rng == {"sheetId": 7, "dimension": "ROWS", "startIndex": 56, "endIndex": 57}


def test_対象がなければ空リスト() -> None:
    assert _build_delete_requests(sheet_id=1, row_numbers=[]) == []
