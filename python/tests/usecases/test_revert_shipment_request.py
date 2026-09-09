from __future__ import annotations

import pytest

from usecases.revert_shipment_request import (
    CLEARED_COLUMNS,
    build_revert_plan,
    build_target_keywords,
    extract_inbound_plan_ids,
    select_chatwork_message_ids,
)


class _Row:
    def __init__(self, row_number: int, alias: str, plan: str = "", name: str = "商品") -> None:
        self.row_number = row_number
        self._d = {"プラン別名": alias, "梱包依頼日": "09/09", "納品プラン": plan, "商品名": name}

    def get(self, key: str) -> str:
        return self._d.get(key, "")


class TestClearedColumns:
    def test_クリアするのは3列だけ(self) -> None:
        assert CLEARED_COLUMNS == ("梱包依頼日", "プラン別名", "納品プラン")

    def test_数量や状態やSKUには触れない(self) -> None:
        for forbidden in ("SKU", "FNSKU", "購入数", "状態", "ASIN", "在庫数", "受領日"):
            assert forbidden not in CLEARED_COLUMNS


class TestBuildRevertPlan:
    def test_指定したプラン別名の行だけを対象にする(self) -> None:
        rows = [_Row(207, "09/09ノーマル"), _Row(300, "09/04ノーマル"), _Row(208, "09/09ノーマル")]
        plan = build_revert_plan(rows, "09/09ノーマル")
        assert [r.row_number for r in plan.rows] == [207, 208]

    def test_行番号の昇順で返す(self) -> None:
        rows = [_Row(225, "09/09ノーマル"), _Row(207, "09/09ノーマル")]
        plan = build_revert_plan(rows, "09/09ノーマル")
        assert [r.row_number for r in plan.rows] == [207, 225]

    def test_前後の空白を無視して一致させる(self) -> None:
        plan = build_revert_plan([_Row(207, " 09/09ノーマル ")], "09/09ノーマル")
        assert [r.row_number for r in plan.rows] == [207]

    def test_該当行が無ければエラー(self) -> None:
        with pytest.raises(ValueError, match="09/09ノーマル"):
            build_revert_plan([_Row(300, "09/04ノーマル")], "09/09ノーマル")

    def test_プラン別名が空の指定は受け付けない(self) -> None:
        with pytest.raises(ValueError):
            build_revert_plan([_Row(207, "09/09ノーマル")], "  ")


class TestExtractInboundPlanIds:
    def test_HYPERLINK数式からフルIDを重複なく取り出す(self) -> None:
        link = '=HYPERLINK("https://x/confirm_content_step?wf=wfa8e9e413-4a48-43f6-b4af-534989fe4c97","wfa8e9e413")'
        rows = [_Row(207, "a", plan=link), _Row(208, "a", plan=link)]
        assert extract_inbound_plan_ids(rows) == ["wfa8e9e413-4a48-43f6-b4af-534989fe4c97"]

    def test_納品プランが空でもエラーにしない(self) -> None:
        assert extract_inbound_plan_ids([_Row(207, "a", plan="")]) == []

    def test_短縮IDしか無ければ拾わない(self) -> None:
        assert extract_inbound_plan_ids([_Row(207, "a", plan="wfa8e9e413")]) == []

    def test_複数のプランIDをすべて返す(self) -> None:
        rows = [
            _Row(207, "a", plan="?wf=wfa8e9e413-4a48-43f6-b4af-534989fe4c97"),
            _Row(208, "a", plan="?wf=wf546a2b78-fc1a-4dd5-8e55-ba49a46c4e0a"),
        ]
        assert len(extract_inbound_plan_ids(rows)) == 2


def _msg(mid: str, account_id: int, send_time: int, body: str) -> dict:
    return {"message_id": mid, "send_time": send_time, "account": {"account_id": account_id}, "body": body}


class TestSelectChatworkMessageIds:
    def test_自分が送った梱包指示書の本文と添付を拾う(self) -> None:
        msgs = [
            _msg("1", 5437457, 1000, "[To:986396]徐雪蘭さん\n【ノーマル】11件の梱包指示書を作成したので送付します。"),
            _msg("2", 5437457, 1001, "[download:1]2026-09-09_ノーマル.pdf[/download]"),
            _msg("3", 5437457, 1002, "[download:2]0909ノーマル指示書.xlsx[/download]"),
            _msg("4", 5437457, 1003, "[download:3]0909ノーマル検品指示書.xlsx[/download]"),
        ]
        keywords = build_target_keywords("09/09ノーマル", 2026)
        got = select_chatwork_message_ids(msgs, account_id=5437457, since=999, keywords=keywords)
        assert got == ["1", "2", "3", "4"]

    def test_同じ日に送った納品ラベルは拾わない(self) -> None:
        msgs = [
            _msg("1", 5437457, 1000, "08/25ノーマルの納品ラベルです。納品番号: FBA15GHML0X3"),
            _msg("2", 5437457, 1001, "[download:9]FBA15GHML0X3_納品ラベル.pdf[/download]"),
            _msg("3", 5437457, 1002, "【ノーマル】11件の梱包指示書を作成したので送付します。"),
        ]
        keywords = build_target_keywords("09/09ノーマル", 2026)
        got = select_chatwork_message_ids(msgs, account_id=5437457, since=999, keywords=keywords)
        assert got == ["3"]

    def test_相手の発言は拾わない(self) -> None:
        msgs = [_msg("1", 986396, 1000, "【ノーマル】11件の梱包指示書")]
        assert select_chatwork_message_ids(msgs, account_id=5437457, since=999, keywords=["梱包指示書"]) == []

    def test_基準時刻より前は拾わない(self) -> None:
        msgs = [_msg("1", 5437457, 500, "【ノーマル】梱包指示書")]
        assert select_chatwork_message_ids(msgs, account_id=5437457, since=999, keywords=["梱包指示書"]) == []

    def test_キーワードに当たらない自分の発言は拾わない(self) -> None:
        msgs = [
            _msg("1", 5437457, 1000, "08/25ノーマルの納品ラベルです。納品番号: FBA15GHML0X3"),
            _msg("2", 5437457, 1001, "【ノーマル】梱包指示書を作成したので送付します。"),
        ]
        got = select_chatwork_message_ids(msgs, account_id=5437457, since=999, keywords=["梱包指示書"])
        assert got == ["2"]

    def test_削除済みは拾わない(self) -> None:
        msgs = [_msg("1", 5437457, 1000, "[deleted]")]
        assert select_chatwork_message_ids(msgs, account_id=5437457, since=999, keywords=["梱包指示書"]) == []


class TestBuildTargetKeywords:
    def test_本文と指示書とラベルの3形式を作る(self) -> None:
        got = build_target_keywords("09/09ノーマル", 2026)
        assert "梱包指示書" in got
        assert "0909ノーマル" in got
        assert "2026-09-09_ノーマル" in got

    def test_ファッション2のような分類名も扱える(self) -> None:
        got = build_target_keywords("08/25ファッション2", 2026)
        assert "0825ファッション2" in got
        assert "2026-08-25_ファッション2" in got

    def test_日付形式でない別名でもファイル名の形は作る(self) -> None:
        got = build_target_keywords("自宅", 2026)
        assert "自宅" in got
