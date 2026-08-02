# shipment items ページング対応 + SKU/FNSKU 納品ベース補完 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 受領完了した shipment の受領数・受領日を仕入管理シートに確実に自動反映させる（`get_shipment_items` のページング取りこぼしを解消し、SKU/FNSKU 欠落行を納品実データで補完する）。

**Architecture:** (1) `InboundPlanCreator.get_shipment_items` を v0 エンドポイントで全ページ取得＋NextTokenループガード＋SellerSKU重複排除に修正。(2) 新ユースケース `fill_sku_fnsku_from_shipment` が納品(shipment)の `SellerSKU↔FNSKU` 対応で空欄を補完（純粋関数 `_resolve_sku_fnsku` に判定を分離）。(3) 補完を `update_status_estimate` の前段で自動実行し、単独CLIコマンド `fill-sku-fnsku` も追加。

**Tech Stack:** Python 3.12+, httpx, gspread, click, pytest。作業ディレクトリ: `procurements/management-helper/python`（独立 git リポジトリ, ブランチ main）。テストは `pytest tests/unit/...`。

---

### Task 1: get_shipment_items のページング対応

**Files:**
- Modify: `src/infrastructure/amazon/inbound_plan_creator.py:154-169`（`get_shipment_items` を置換、直上に定数 `MAX_ITEM_PAGES` 追加、`_fetch_items_page` 追加）
- Test: `tests/unit/test_get_shipment_items_pagination.py`（新規）

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_get_shipment_items_pagination.py`:

```python
from __future__ import annotations

from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator


def _creator_with_pages(pages):
    creator = InboundPlanCreator("dummy-token")
    calls = {"i": 0}

    def fake_fetch(shipment_id, next_token):
        i = calls["i"]
        calls["i"] += 1
        return pages[i]

    creator._fetch_items_page = fake_fetch
    return creator


def test_aggregates_multiple_pages_dedup_by_sku():
    pages = [
        ([{"SellerSKU": "A", "QuantityReceived": 5}], "t1"),
        ([{"SellerSKU": "B", "QuantityReceived": 3}], "t2"),
        ([{"SellerSKU": "A", "QuantityReceived": 5}], "t1"),
    ]
    creator = _creator_with_pages(pages)
    items = creator.get_shipment_items("FBAXXXXXXXXX")
    skus = sorted(i["SellerSKU"] for i in items)
    assert skus == ["A", "B"]


def test_looping_same_page_does_not_infinite_loop():
    same = ([{"SellerSKU": "A", "QuantityReceived": 41},
             {"SellerSKU": "B", "QuantityReceived": 6}], "loop-token")
    creator = _creator_with_pages([same] * 100)
    items = creator.get_shipment_items("FBAXXXXXXXXX")
    assert sorted(i["SellerSKU"] for i in items) == ["A", "B"]


def test_single_page_no_token():
    creator = _creator_with_pages([([{"SellerSKU": "A", "QuantityReceived": 1}], None)])
    items = creator.get_shipment_items("FBAXXXXXXXXX")
    assert [i["SellerSKU"] for i in items] == ["A"]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python3 -m pytest tests/unit/test_get_shipment_items_pagination.py -v`
Expected: FAIL（現行 `get_shipment_items` は `_fetch_items_page` を使わず httpx を直接呼ぶため、モックが効かず実HTTP発行で失敗、または挙動不一致）

- [ ] **Step 3: 最小実装（get_shipment_items 置換 + _fetch_items_page 追加）**

`src/infrastructure/amazon/inbound_plan_creator.py` の `API_BASE_V0 = ...` 行の直後に定数追加:

```python
MAX_ITEM_PAGES = 50
```

`get_shipment_items`（現 154-169行）を以下で置換:

```python
    def get_shipment_items(self, shipment_id: str) -> list[dict[str, Any]]:
        items_by_sku: dict[str, dict[str, Any]] = {}
        seen_tokens: set[str] = set()
        next_token: str | None = None
        for _ in range(MAX_ITEM_PAGES):
            page_items, next_token = self._fetch_items_page(shipment_id, next_token)
            added_new = False
            for item in page_items:
                sku = str(item.get("SellerSKU", item.get("msku", item.get("sellerSku", "")))).strip()
                if not sku or sku in items_by_sku:
                    continue
                items_by_sku[sku] = item
                added_new = True
            if not next_token or next_token in seen_tokens or not added_new:
                break
            seen_tokens.add(next_token)
        return list(items_by_sku.values())

    def _fetch_items_page(
        self, shipment_id: str, next_token: str | None
    ) -> tuple[list[dict[str, Any]], str | None]:
        url = f"{API_BASE_V0}/shipments/{shipment_id}/items"
        params: dict[str, Any] = {"MarketplaceId": DEFAULT_MARKETPLACE_ID}
        if next_token:
            params["NextToken"] = next_token
        response = httpx.get(url, params=params, headers=self._headers, timeout=30.0)
        data = response.json()
        payload = data.get("payload", {})
        return payload.get("ItemData", []), payload.get("NextToken")
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python3 -m pytest tests/unit/test_get_shipment_items_pagination.py -v`
Expected: PASS（3件）

- [ ] **Step 5: コミット**

```bash
git add src/infrastructure/amazon/inbound_plan_creator.py tests/unit/test_get_shipment_items_pagination.py
git commit -m "fix(sp-api): get_shipment_items を全ページ取得+重複排除+ループ防止に修正

CLOSED shipment で行SKUが後続ページにあると受領を取りこぼす問題を解消。
v0エンドポイントを正とし NextToken を辿る(ループ検出/SellerSKU重複排除)。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 補完判定の純粋関数 `_resolve_sku_fnsku`

**Files:**
- Create: `src/usecases/fill_sku_fnsku_from_shipment.py`（この Task では `_resolve_sku_fnsku` のみ）
- Test: `tests/unit/test_resolve_sku_fnsku.py`（新規）

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_resolve_sku_fnsku.py`:

```python
from __future__ import annotations

from usecases.fill_sku_fnsku_from_shipment import _resolve_sku_fnsku


# pairs: list[tuple[sku, fnsku]]
def test_fill_fnsku_when_sku_present():
    pairs = [("DB-T0OT-ZDCG", "X001APUHB1"), ("DL-H48F-39WT", "X002")]
    sku, fnsku = _resolve_sku_fnsku("DB-T0OT-ZDCG", "", pairs, asin="", asin_map={})
    assert sku is None and fnsku == "X001APUHB1"


def test_fill_sku_when_fnsku_present():
    pairs = [("DB-T0OT-ZDCG", "X001APUHB1")]
    sku, fnsku = _resolve_sku_fnsku("", "X001APUHB1", pairs, asin="", asin_map={})
    assert sku == "DB-T0OT-ZDCG" and fnsku is None


def test_both_empty_single_pair_fills_both():
    pairs = [("DB-T0OT-ZDCG", "X001APUHB1")]
    sku, fnsku = _resolve_sku_fnsku("", "", pairs, asin="B0FCHM6QQR", asin_map={})
    assert sku == "DB-T0OT-ZDCG" and fnsku == "X001APUHB1"


def test_both_empty_multi_pair_uses_asin_map():
    pairs = [("DB-T0OT-ZDCG", "X001APUHB1"), ("DL-H48F-39WT", "X002")]
    asin_map = {"B0FCHM6QQR": ("DB-T0OT-ZDCG", "X001APUHB1")}
    sku, fnsku = _resolve_sku_fnsku("", "", pairs, asin="B0FCHM6QQR", asin_map=asin_map)
    assert sku == "DB-T0OT-ZDCG" and fnsku == "X001APUHB1"


def test_both_empty_multi_pair_ambiguous_returns_none():
    pairs = [("DB-T0OT-ZDCG", "X001APUHB1"), ("DL-H48F-39WT", "X002")]
    sku, fnsku = _resolve_sku_fnsku("", "", pairs, asin="B0UNKNOWN", asin_map={})
    assert sku is None and fnsku is None


def test_no_matching_pair_returns_none():
    pairs = [("OTHER", "XZZZ")]
    sku, fnsku = _resolve_sku_fnsku("DB-T0OT-ZDCG", "", pairs, asin="", asin_map={})
    assert sku is None and fnsku is None
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python3 -m pytest tests/unit/test_resolve_sku_fnsku.py -v`
Expected: FAIL（`fill_sku_fnsku_from_shipment` モジュール／`_resolve_sku_fnsku` 未定義の ImportError）

- [ ] **Step 3: 最小実装**

`src/usecases/fill_sku_fnsku_from_shipment.py`（新規、この Task ではこの関数まで）:

```python
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _resolve_sku_fnsku(
    cur_sku: str,
    cur_fnsku: str,
    pairs: list[tuple[str, str]],
    asin: str,
    asin_map: dict[str, tuple[str, str]],
) -> tuple[str | None, str | None]:
    if cur_sku and not cur_fnsku:
        for sku, fnsku in pairs:
            if sku == cur_sku:
                return None, (fnsku or None)
        return None, None
    if cur_fnsku and not cur_sku:
        for sku, fnsku in pairs:
            if fnsku == cur_fnsku:
                return (sku or None), None
        return None, None
    if not cur_sku and not cur_fnsku:
        if len(pairs) == 1:
            sku, fnsku = pairs[0]
            return (sku or None), (fnsku or None)
        candidate = asin_map.get(asin)
        if candidate and any(candidate[0] == sku for sku, _ in pairs):
            return candidate[0] or None, candidate[1] or None
        return None, None
    return None, None
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python3 -m pytest tests/unit/test_resolve_sku_fnsku.py -v`
Expected: PASS（6件）

- [ ] **Step 5: コミット**

```bash
git add src/usecases/fill_sku_fnsku_from_shipment.py tests/unit/test_resolve_sku_fnsku.py
git commit -m "feat(fill-sku): 補完判定の純粋関数 _resolve_sku_fnsku を追加

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: fill_sku_fnsku_from_shipment オーケストレーション

**Files:**
- Modify: `src/usecases/fill_sku_fnsku_from_shipment.py`（`fill_sku_fnsku_from_shipment` と補助関数を追加）
- Test: `tests/unit/test_fill_sku_fnsku_from_shipment.py`（新規）

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_fill_sku_fnsku_from_shipment.py`:

```python
from __future__ import annotations

from usecases import fill_sku_fnsku_from_shipment as mod


class FakeWorksheet:
    def __init__(self, values):
        self._values = values
        self.batched = []

    def get_all_values(self):
        return self._values

    def batch_update(self, data, value_input_option=None):
        self.batched.append((data, value_input_option))


class FakeRepo:
    def __init__(self, ws):
        self._ws = ws

    def open_worksheet(self, sheet_id, sheet_name):
        return self._ws


class FakeConfig:
    sheet_id = "SID"
    purchase_sheet_name = "仕入管理"
    api_key = "k"
    api_secret = "s"
    refresh_token = "r"


class FakeCreator:
    def __init__(self, items_by_shipment):
        self._items = items_by_shipment

    def get_shipment_items(self, shipment_id):
        return self._items.get(shipment_id, [])


def _sheet_values():
    # HEADER_ROW=4。ヘッダーに 状態/ASIN/SKU/FNSKU/納品プラン
    header = ["状態", "ASIN", "SKU", "FNSKU", "納品プラン"]
    return [
        ["", "", "", "", ""],
        ["", "", "", "", ""],
        ["", "", "", "", ""],
        header,
        ["発送済み", "B0FCHM6QQR", "DB-T0OT-ZDCG", "", "FBA15G8F5BCV"],  # 行5: FNSKU補完
        ["在庫あり", "B0X", "SKU-X", "FN-X", "FBA15GAAAAAA"],             # 行6: 対象外(状態)
        ["自宅発送", "B0Y", "", "", "FBA15GBBBBBB"],                     # 行7: 単一SKUで両方補完
    ]


def test_fills_missing_fnsku_and_both(monkeypatch):
    ws = FakeWorksheet(_sheet_values())
    repo = FakeRepo(ws)
    items = {
        "FBA15G8F5BCV": [{"SellerSKU": "DB-T0OT-ZDCG", "FulfillmentNetworkSKU": "X001APUHB1"}],
        "FBA15GBBBBBB": [{"SellerSKU": "YY-SKU", "FulfillmentNetworkSKU": "X009"}],
    }
    monkeypatch.setattr(mod, "get_auth_token", lambda *a, **k: "tok")
    monkeypatch.setattr(mod, "InboundPlanCreator", lambda tok: FakeCreator(items))

    mod.fill_sku_fnsku_from_shipment(FakeConfig(), repo)

    # batch_update に行5のFNSKU=X001APUHB1、行7のSKU=YY-SKU/FNSKU=X009 が含まれる
    flat = []
    for data, _ in ws.batched:
        flat.extend(data)
    cells = {d["range"]: d["values"][0][0] for d in flat}
    # FNSKU列=D(4列目), SKU列=C(3列目)
    assert cells.get("D5") == "X001APUHB1"
    assert cells.get("C7") == "YY-SKU"
    assert cells.get("D7") == "X009"
    # 行6(在庫あり)は触らない
    assert "C6" not in cells and "D6" not in cells


def test_noop_when_nothing_to_fill(monkeypatch):
    header = ["状態", "ASIN", "SKU", "FNSKU", "納品プラン"]
    values = [["", "", "", "", ""]] * 3 + [header, ["発送済み", "B0Z", "SKU-Z", "FN-Z", "FBA15GCCCCCC"]]
    ws = FakeWorksheet(values)
    monkeypatch.setattr(mod, "get_auth_token", lambda *a, **k: "tok")
    monkeypatch.setattr(mod, "InboundPlanCreator", lambda tok: FakeCreator({}))
    mod.fill_sku_fnsku_from_shipment(FakeConfig(), FakeRepo(ws))
    assert ws.batched == []
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python3 -m pytest tests/unit/test_fill_sku_fnsku_from_shipment.py -v`
Expected: FAIL（`fill_sku_fnsku_from_shipment` / `get_auth_token` / `InboundPlanCreator` 未定義）

- [ ] **Step 3: 最小実装（fill_sku_fnsku_from_shipment.py に追記）**

`src/usecases/fill_sku_fnsku_from_shipment.py` の先頭 import 群と本体を以下に更新（既存の `_resolve_sku_fnsku` は残す）:

```python
from __future__ import annotations

import logging
import re

import gspread

from shared.config import AppConfig
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)

TARGET_STATUSES = ["発送済み", "自宅発送", "納品中"]
STATUS_COL = "状態"
ASIN_COL = "ASIN"
SKU_COL = "SKU"
FNSKU_COL = "FNSKU"
PLAN_COL = "納品プラン"


def fill_sku_fnsku_from_shipment(config: AppConfig, repo: BaseSheetsRepository) -> None:
    creator = InboundPlanCreator(
        get_auth_token(config.api_key, config.api_secret, config.refresh_token)
    )
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sku_col = sheet._get_column_index_by_name(SKU_COL) + 1
    fnsku_col = sheet._get_column_index_by_name(FNSKU_COL) + 1
    asin_map = _build_asin_map(sheet)
    pairs_cache: dict[str, list[tuple[str, str]]] = {}

    updates: list[dict] = []
    for row in sheet.all_data:
        if str(row.get(STATUS_COL) or "").strip() not in TARGET_STATUSES:
            continue
        cur_sku = str(row.get(SKU_COL) or "").strip()
        cur_fnsku = str(row.get(FNSKU_COL) or "").strip()
        if cur_sku and cur_fnsku:
            continue
        shipment_id = _extract_shipment_id(str(row.get(PLAN_COL) or ""))
        if not shipment_id:
            continue
        pairs = _get_pairs(creator, shipment_id, pairs_cache)
        asin = str(row.get(ASIN_COL) or "").strip()
        new_sku, new_fnsku = _resolve_sku_fnsku(cur_sku, cur_fnsku, pairs, asin, asin_map)
        if new_sku and not cur_sku:
            updates.append({"range": gspread.utils.rowcol_to_a1(row.row_number, sku_col), "values": [[new_sku]]})
        if new_fnsku and not cur_fnsku:
            updates.append({"range": gspread.utils.rowcol_to_a1(row.row_number, fnsku_col), "values": [[new_fnsku]]})

    if updates:
        sheet._worksheet.batch_update(updates, value_input_option="USER_ENTERED")
    logger.info("SKU/FNSKU補完: %d セル書き込み", len(updates))


def _extract_shipment_id(cell_value: str) -> str:
    m = re.search(r"(FBA[A-Z0-9]{9})", cell_value)
    return m.group(1) if m else ""


def _build_asin_map(sheet: PurchaseSheet) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for row in sheet.all_data:
        asin = str(row.get(ASIN_COL) or "").strip()
        sku = str(row.get(SKU_COL) or "").strip()
        fnsku = str(row.get(FNSKU_COL) or "").strip()
        if asin and sku and asin not in result:
            result[asin] = (sku, fnsku)
    return result


def _get_pairs(
    creator: InboundPlanCreator, shipment_id: str, cache: dict[str, list[tuple[str, str]]]
) -> list[tuple[str, str]]:
    if shipment_id in cache:
        return cache[shipment_id]
    pairs: list[tuple[str, str]] = []
    try:
        for item in creator.get_shipment_items(shipment_id):
            sku = str(item.get("SellerSKU", item.get("msku", item.get("sellerSku", "")))).strip()
            fnsku = str(item.get("FulfillmentNetworkSKU", item.get("fulfillmentNetworkSku", ""))).strip()
            if sku:
                pairs.append((sku, fnsku))
    except Exception as e:
        logger.warning("shipment items取得失敗 (%s): %s", shipment_id, e)
    cache[shipment_id] = pairs
    return pairs
```

（末尾に既存の `_resolve_sku_fnsku` を残すこと）

- [ ] **Step 4: テストが通ることを確認**

Run: `python3 -m pytest tests/unit/test_fill_sku_fnsku_from_shipment.py tests/unit/test_resolve_sku_fnsku.py -v`
Expected: PASS（8件）

- [ ] **Step 5: コミット**

```bash
git add src/usecases/fill_sku_fnsku_from_shipment.py tests/unit/test_fill_sku_fnsku_from_shipment.py
git commit -m "feat(fill-sku): 納品ベースSKU/FNSKU補完ユースケースを実装

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 統合（update-status 前段 + CLIコマンド + バージョン）

**Files:**
- Modify: `src/usecases/update_status_estimate.py:21-25`（補完を前段呼び出し）
- Modify: `main.py`（`fill-sku-fnsku` コマンド追加）
- Modify: `pyproject.toml:7`（0.8.0 → 0.9.0）
- Test: `tests/unit/test_update_status_calls_fill.py`（新規）

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_update_status_calls_fill.py`:

```python
from __future__ import annotations

from usecases import update_status_estimate as mod


def test_update_status_calls_fill_first(monkeypatch):
    calls = []
    monkeypatch.setattr(mod, "get_auth_token", lambda *a, **k: "tok")
    monkeypatch.setattr(mod, "InboundPlanCreator", lambda tok: object())
    monkeypatch.setattr(mod, "fill_sku_fnsku_from_shipment", lambda config, repo: calls.append("fill"))

    class FakeSheet:
        data = []
        def __init__(self, *a, **k): pass
        def filter(self, *a, **k): calls.append("filter")

    monkeypatch.setattr(mod, "PurchaseSheet", FakeSheet)

    mod.update_status_estimate(config=object(), repo=object())
    assert calls and calls[0] == "fill"  # 補完が最初に走る
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python3 -m pytest tests/unit/test_update_status_calls_fill.py -v`
Expected: FAIL（`fill_sku_fnsku_from_shipment` が update_status_estimate に import されていない）

- [ ] **Step 3: 実装（update_status_estimate.py 修正）**

`src/usecases/update_status_estimate.py` の import 群（先頭付近）に追加:

```python
from usecases.fill_sku_fnsku_from_shipment import fill_sku_fnsku_from_shipment
```

`update_status_estimate` 関数の本体先頭（現 22行目 `access_token = ...` の直前）に追加:

```python
    fill_sku_fnsku_from_shipment(config, repo)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python3 -m pytest tests/unit/test_update_status_calls_fill.py -v`
Expected: PASS

- [ ] **Step 5: main.py に CLIコマンド追加**

`main.py` の `archive_out_of_stock` コマンド定義（127-131行）の直後に追加:

```python
@cli.command()
def fill_sku_fnsku() -> None:
    from usecases.fill_sku_fnsku_from_shipment import fill_sku_fnsku_from_shipment
    config, repo = _get_config_and_repo()
    fill_sku_fnsku_from_shipment(config, repo)
```

- [ ] **Step 6: コマンド登録とフルテストを確認**

Run: `python3 main.py fill-sku-fnsku --help && python3 -m pytest tests/unit -q`
Expected: help表示、全テスト PASS

- [ ] **Step 7: バージョン更新（pyproject.toml:7）**

`version = "0.8.0"` を `version = "0.9.0"` に変更。

- [ ] **Step 8: コミット**

```bash
git add src/usecases/update_status_estimate.py main.py pyproject.toml
git commit -m "feat(update-status): 受領照合の前段でSKU/FNSKU補完を自動実行 (v0.9.0)

fill-sku-fnsku 単独コマンドも追加。補完→受領照合の順で走らせ、
ページング修正と併せて受領済みshipmentの在庫数/受領日を反映させる。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 完了後の実運用手順（プラン外・手動確認用）

1. `python3 main.py fill-sku-fnsku` を実行し補完セル数を確認。
2. `python3 main.py update-status` を実行し「納品済み」ログと在庫数書き込み件数を確認。
3. launchd `com.wada.update-status-estimate` は補完を内包するため plist 変更不要（順序: 補完→status→inventory→archive は既存スケジュールで充足）。

## Self-Review 結果
- **spec カバレッジ**: 修正1=Task1 / 修正2=Task2,3 / 統合(前段+単独コマンド)=Task4 / TDD=各Task。網羅。
- **プレースホルダ**: なし（全ステップに実コード）。
- **型整合**: `_resolve_sku_fnsku(cur_sku, cur_fnsku, pairs, asin, asin_map)` の呼び出し（Task3）と定義（Task2）一致。`_fetch_items_page` 戻り値 `(items, next_token)` と利用一致。`get_shipment_items` 戻り値 `list[dict]` は既存 `_sum_quantities_for_sku` と互換。
