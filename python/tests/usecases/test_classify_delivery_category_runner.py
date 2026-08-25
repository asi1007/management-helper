"""複数ASINをまとめて判定するランナーのテスト"""
from __future__ import annotations

import pytest

from usecases.classify_delivery_category import ClassificationResult, run_classification


@pytest.fixture
def patched(mocker):
    mocker.patch("usecases.classify_delivery_category.get_auth_token", return_value="token")
    sales = mocker.Mock()
    creator = mocker.Mock()
    mocker.patch("usecases.classify_delivery_category.SalesSheet", return_value=sales)
    mocker.patch("usecases.classify_delivery_category.InboundPlanCreator", return_value=creator)
    classify = mocker.patch("usecases.classify_delivery_category.classify_delivery_category")
    return classify


def test_複数ASINを順に処理する(patched, mocker):
    patched.side_effect = [
        ClassificationResult(asin="B001", category="ノーマル"),
        ClassificationResult(asin="B002", category="ファッション"),
    ]

    outcomes = run_classification(mocker.Mock(), mocker.Mock(), ["B001", "B002"])

    assert [o.asin for o in outcomes] == ["B001", "B002"]
    assert [o.result.category for o in outcomes] == ["ノーマル", "ファッション"]
    assert all(not o.error for o in outcomes)


def test_1件失敗しても残りを処理しエラーを保持する(patched, mocker):
    patched.side_effect = [
        RuntimeError("SKUが解決できません"),
        ClassificationResult(asin="B002", category="ノーマル"),
    ]

    outcomes = run_classification(mocker.Mock(), mocker.Mock(), ["B001", "B002"])

    assert outcomes[0].result is None
    assert "SKU" in outcomes[0].error
    assert outcomes[1].result.category == "ノーマル"


def test_オプションはそのまま渡される(patched, mocker):
    patched.return_value = ClassificationResult(asin="B001", category="ノーマル")

    run_classification(mocker.Mock(), mocker.Mock(), ["B001"], overwrite=True, dry_run=True)

    kwargs = patched.call_args.kwargs
    assert kwargs["overwrite"] is True
    assert kwargs["dry_run"] is True
