# /batch-labels FC分割 pre-check 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/batch-labels` 実行時にラベル生成前に SP-API 試作プランで FC 分割を事前検知し、分割があれば停止、無ければ「納品プラン」列に試作プラン URL を書き込んで処理続行する。

**Architecture:** `batch_print_labels()` の SKU/FNSKU validation 直後に `_check_fc_split_for_all_groups()` を挿入。各グループで `InboundPlanCreator.create_plan()` を呼び、新規 `get_packing_groups()` で packingGroups を取得。1グループなら URL 書き込み続行、2+ なら全グループ走査後に RuntimeError + 振り分け表示。all-or-nothing 方針。

**Tech Stack:** Python 3.14, pytest (+pytest-mock), httpx, gspread, SP-API (FBA Inbound 2024-03-20)

**Spec:** `docs/superpowers/specs/2026-05-29-batch-labels-fc-split-design.md`

---

## File Structure

| ファイル | 変更内容 |
|---|---|
| `python/src/infrastructure/amazon/inbound_plan_creator.py` | `get_packing_groups()` メソッド追加 |
| `python/src/usecases/batch_print_labels.py` | `_check_fc_split_for_all_groups()` 等のヘルパー追加、`batch_print_labels()` から呼び出し |
| `python/tests/infrastructure/amazon/test_inbound_plan_creator.py` | `get_packing_groups` のテスト追加 |
| `python/tests/usecases/test_batch_labels_fc_split.py` | 新規ファイル (TDD) |
| `procurements/management-helper/.claude/commands/batch-labels.md` | ドキュメント更新 (事前確認自動化) |
| `procurements/fullfilment/.claude/commands/update-fulfillment.md` | ドキュメント更新 (batch-labels連携運用、URL再利用) |
| `python/pyproject.toml` | バージョン bump (`0.6.0` → `0.7.0`、マイナー: 新機能追加) |

---

## Task 1: `InboundPlanCreator.get_packing_groups()` 追加

**Files:**
- Modify: `python/src/infrastructure/amazon/inbound_plan_creator.py:187-195`
- Test: `python/tests/infrastructure/amazon/test_inbound_plan_creator.py`

既存 `get_packing_group_id()` (1件しか返さない) のリスト版を追加。SP-API `GET /inboundPlans/{id}/packingGroups` のレスポンス `packingGroups` リストをそのまま返す。

- [ ] **Step 1: Write the failing test**

`python/tests/infrastructure/amazon/test_inbound_plan_creator.py` の末尾に追加:

```python
def test_get_packing_groups_returns_list(mocker):
    creator = InboundPlanCreator("token")
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {
        "packingGroups": [
            {"packingGroupId": "pg-aaa"},
            {"packingGroupId": "pg-bbb"},
        ]
    }
    mock_resp.raise_for_status = mocker.Mock()
    mock_get = mocker.patch(
        "infrastructure.amazon.inbound_plan_creator.httpx.get", return_value=mock_resp
    )

    groups = creator.get_packing_groups("wf123")

    assert len(groups) == 2
    assert groups[0]["packingGroupId"] == "pg-aaa"
    called_url = mock_get.call_args[0][0]
    assert called_url.endswith("/inboundPlans/wf123/packingGroups")


def test_get_packing_groups_empty_when_no_data(mocker):
    creator = InboundPlanCreator("token")
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {}
    mock_resp.raise_for_status = mocker.Mock()
    mocker.patch(
        "infrastructure.amazon.inbound_plan_creator.httpx.get", return_value=mock_resp
    )

    assert creator.get_packing_groups("wf000") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/wadaatsushi/Documents/automation/procurements/management-helper/python
PYTHONPATH=src python3 -m pytest tests/infrastructure/amazon/test_inbound_plan_creator.py::test_get_packing_groups_returns_list -v
```
Expected: FAIL with `AttributeError: 'InboundPlanCreator' object has no attribute 'get_packing_groups'`

- [ ] **Step 3: Write minimal implementation**

`python/src/infrastructure/amazon/inbound_plan_creator.py` の `get_packing_group_id()` (187-195行) の**直後**に追加:

```python
    def get_packing_groups(self, inbound_plan_id: str) -> list[dict[str, Any]]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/packingGroups"
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("packingGroups", [])
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
PYTHONPATH=src python3 -m pytest tests/infrastructure/amazon/test_inbound_plan_creator.py -v
```
Expected: 全 PASS (既存テスト + 新規2件)

- [ ] **Step 5: Commit**

```bash
git add python/src/infrastructure/amazon/inbound_plan_creator.py python/tests/infrastructure/amazon/test_inbound_plan_creator.py
git commit -m "$(cat <<'EOF'
feat(inbound-plan): InboundPlanCreator に get_packing_groups() を追加

packingGroupsレスポンス全件を返すリスト版。FC分割数判定に使う。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: FC分割チェック関数の骨組み (1グループ正常系)

**Files:**
- Modify: `python/src/usecases/batch_print_labels.py` (新規ヘルパー追加)
- Test: `python/tests/usecases/test_batch_labels_fc_split.py` (新規)

`_check_fc_split_for_all_groups()` を新規実装。まず1グループ正常系のテストから。

- [ ] **Step 1: Write the failing test**

`python/tests/usecases/test_batch_labels_fc_split.py` を新規作成:

```python
"""FC分割pre-checkのテスト"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest
from src.usecases.batch_print_labels import _check_fc_split_for_all_groups


def _row(row_number: int, sku: str, asin: str = "B000ASIN", qty: int = 100) -> SimpleNamespace:
    mapping = {"SKU": sku, "ASIN": asin, "FNSKU": f"X001{sku}", "購入数": qty, "納品分類": "ノーマル"}
    return SimpleNamespace(row_number=row_number, get=lambda k, _m=mapping: _m.get(k))


def _make_creator_mock(mocker, plan_id: str, packing_groups: list[dict]) -> object:
    creator = mocker.Mock()
    creator.create_plan.return_value = {
        "inboundPlanId": plan_id,
        "link": f"https://sellercentral.amazon.co.jp/fba/sendtoamazon/confirm_content_step?wf={plan_id}",
    }
    creator.get_packing_groups.return_value = packing_groups
    return creator


def test_check_fc_split_single_group_passes(mocker):
    """1 packingGroup なら例外なし、シートに納品プラン URL を書き込む"""
    rows = [_row(340, "SKU_A"), _row(341, "SKU_B")]
    groups = {"ノーマル": rows}
    sheet = mocker.Mock()
    creator = _make_creator_mock(mocker, "wf111", [{"packingGroupId": "pg-a"}])

    _check_fc_split_for_all_groups(groups, creator, sheet)

    creator.create_plan.assert_called_once()
    creator.get_packing_groups.assert_called_once_with("wf111")
    # 「納品プラン」列に試作プラン URL が書き込まれた
    sheet.write_trial_plan_url.assert_called_once()
    call_args = sheet.write_trial_plan_url.call_args
    assert call_args.args[0] == rows  # 行リスト
    assert "wf111" in call_args.args[1]  # URL or plan_id
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=src python3 -m pytest tests/usecases/test_batch_labels_fc_split.py::test_check_fc_split_single_group_passes -v
```
Expected: FAIL with `ImportError: cannot import name '_check_fc_split_for_all_groups'`

- [ ] **Step 3: Write minimal implementation**

`python/src/usecases/batch_print_labels.py` の `_validate_sku_fnsku()` (136-156行) の**直後**に追加:

```python
def _check_fc_split_for_all_groups(
    non_home_groups: dict[str, list[BaseRow]],
    creator: Any,
    sheet: Any,
) -> None:
    """各グループで試作プランを作成し packingGroups の数を取得。1グループ→URL書き込み、2+→RuntimeError"""
    split_reports: list[str] = []
    plan_results: list[tuple[str, list[BaseRow], str, str]] = []  # (category, rows, plan_id, plan_url)

    for category, rows in non_home_groups.items():
        items = _build_items_from_rows(rows)
        result = creator.create_plan(items)
        plan_id = result["inboundPlanId"]
        plan_url = result["link"]

        groups = creator.get_packing_groups(plan_id)
        if len(groups) > 1:
            sku_to_row = {str(r.get("SKU") or "").strip(): r.row_number for r in rows}
            split_reports.append(_format_split_report(category, plan_id, plan_url, groups, sku_to_row))
        else:
            plan_results.append((category, rows, plan_id, plan_url))

    if split_reports:
        click.echo("\n".join(split_reports), err=True)
        raise RuntimeError(
            f"FC分割を検知 ({len(split_reports)}グループ)。"
            "仕入管理シートの「納品分類」列をグループ別に書き換えてから再実行してください。"
        )

    for _category, rows, plan_id, plan_url in plan_results:
        sheet.write_trial_plan_url(rows, plan_url, plan_id)


def _build_items_from_rows(rows: list[BaseRow]) -> dict[str, dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    for row in rows:
        sku = str(row.get("SKU") or "").strip()
        asin = str(row.get("ASIN") or "").strip()
        try:
            quantity = int(row.get("購入数") or 0)
        except (ValueError, TypeError):
            quantity = 0
        if not sku or quantity <= 0:
            continue
        if sku not in aggregated:
            aggregated[sku] = {"msku": sku, "asin": asin, "quantity": 0, "labelOwner": "SELLER"}
        aggregated[sku]["quantity"] += quantity
    return aggregated


def _format_split_report(
    category: str,
    plan_id: str,
    plan_url: str,
    packing_groups: list[dict[str, Any]],
    sku_to_row: dict[str, int],
) -> str:
    lines = [f"\n[{category}] 試作プラン: {plan_id} ({len(packing_groups)}グループに分割)"]
    for i, pg in enumerate(packing_groups, 1):
        pg_id = pg.get("packingGroupId", "")
        items = pg.get("items", [])
        skus = [str(it.get("msku", "")).strip() for it in items if it.get("msku")]
        row_numbers = sorted({sku_to_row[s] for s in skus if s in sku_to_row})
        rows_str = ", ".join(str(r) for r in row_numbers) if row_numbers else "(行不明)"
        lines.append(f"  グループ{i} ({pg_id}): 行{rows_str} ({len(skus)} SKUs)")
    lines.append(f"  プランURL: {plan_url}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
PYTHONPATH=src python3 -m pytest tests/usecases/test_batch_labels_fc_split.py -v
```
Expected: PASS (`test_check_fc_split_single_group_passes` PASS)

- [ ] **Step 5: Commit**

```bash
git add python/src/usecases/batch_print_labels.py python/tests/usecases/test_batch_labels_fc_split.py
git commit -m "$(cat <<'EOF'
feat(batch-labels): FC分割pre-check の正常系を実装

1 packingGroup → 試作プラン URL を sheet に書き込み続行。
分割検知のロジックは次タスクで実装。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 分割検知時の RuntimeError + 振り分け表示

**Files:**
- Test: `python/tests/usecases/test_batch_labels_fc_split.py` (追記)

- [ ] **Step 1: Write the failing test**

`python/tests/usecases/test_batch_labels_fc_split.py` の末尾に追加:

```python
def test_check_fc_split_two_groups_raises(mocker):
    """2 packingGroups なら RuntimeError、行番号が表示される"""
    rows = [_row(340, "SKU_A"), _row(341, "SKU_B"), _row(342, "SKU_C")]
    groups = {"ノーマル": rows}
    sheet = mocker.Mock()
    packing_groups = [
        {"packingGroupId": "pg-aaa", "items": [{"msku": "SKU_A"}, {"msku": "SKU_B"}]},
        {"packingGroupId": "pg-bbb", "items": [{"msku": "SKU_C"}]},
    ]
    creator = _make_creator_mock(mocker, "wf222", packing_groups)

    with pytest.raises(RuntimeError, match=r"FC分割を検知"):
        _check_fc_split_for_all_groups(groups, creator, sheet)

    # 分割時は URL 書き込みなし
    sheet.write_trial_plan_url.assert_not_called()


def test_check_fc_split_report_contains_row_numbers(mocker, capsys):
    """分割時に各グループのSKUと行番号が表示される"""
    rows = [_row(340, "SKU_A"), _row(341, "SKU_B"), _row(342, "SKU_C")]
    groups = {"ノーマル": rows}
    sheet = mocker.Mock()
    packing_groups = [
        {"packingGroupId": "pg-aaa", "items": [{"msku": "SKU_A"}, {"msku": "SKU_B"}]},
        {"packingGroupId": "pg-bbb", "items": [{"msku": "SKU_C"}]},
    ]
    creator = _make_creator_mock(mocker, "wf333", packing_groups)

    with pytest.raises(RuntimeError):
        _check_fc_split_for_all_groups(groups, creator, sheet)

    captured = capsys.readouterr()
    out = captured.err + captured.out
    assert "ノーマル" in out
    assert "wf333" in out
    assert "340" in out
    assert "341" in out
    assert "342" in out
    assert "pg-aaa" in out
    assert "pg-bbb" in out


def test_check_fc_split_multiple_groups_split(mocker, capsys):
    """複数グループそれぞれが分割した場合、両方のサマリーが表示される"""
    rows_n = [_row(340, "N_A"), _row(341, "N_B")]
    rows_f = [_row(350, "F_A"), _row(351, "F_B")]
    groups = {"ノーマル": rows_n, "ファッション": rows_f}
    sheet = mocker.Mock()

    creator = mocker.Mock()
    creator.create_plan.side_effect = [
        {"inboundPlanId": "wfN1", "link": "url-N"},
        {"inboundPlanId": "wfF1", "link": "url-F"},
    ]
    creator.get_packing_groups.side_effect = [
        [
            {"packingGroupId": "pg-n1", "items": [{"msku": "N_A"}]},
            {"packingGroupId": "pg-n2", "items": [{"msku": "N_B"}]},
        ],
        [
            {"packingGroupId": "pg-f1", "items": [{"msku": "F_A"}]},
            {"packingGroupId": "pg-f2", "items": [{"msku": "F_B"}]},
        ],
    ]

    with pytest.raises(RuntimeError, match=r"2グループ"):
        _check_fc_split_for_all_groups(groups, creator, sheet)

    captured = capsys.readouterr()
    out = captured.err + captured.out
    assert "ノーマル" in out
    assert "ファッション" in out
    assert "wfN1" in out
    assert "wfF1" in out
```

- [ ] **Step 2: Run tests to verify they pass**

Task 2 の実装で既に分割ロジックが入っているので、これらのテストは PASS するはず。確認のため実行:

```bash
PYTHONPATH=src python3 -m pytest tests/usecases/test_batch_labels_fc_split.py -v
```
Expected: 4件全 PASS

- [ ] **Step 3: Commit**

```bash
git add python/tests/usecases/test_batch_labels_fc_split.py
git commit -m "$(cat <<'EOF'
test(batch-labels): FC分割検知時のRuntimeErrorと振り分け表示を検証

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 一部グループのみ分割した場合のテスト

**Files:**
- Test: `python/tests/usecases/test_batch_labels_fc_split.py` (追記)

複数グループのうち一部だけ分割した場合、分割したグループだけサマリーに含めて停止。OK だったグループの URL は書き込まれない (all-or-nothing 方針)。

- [ ] **Step 1: Write the failing test**

```python
def test_check_fc_split_partial_split_blocks_all_writes(mocker, capsys):
    """グループA: 1個 OK, グループB: 2個分割 → 全グループ停止、A の URL も書き込まれない"""
    rows_a = [_row(340, "A_1")]
    rows_b = [_row(350, "B_1"), _row(351, "B_2")]
    groups = {"ノーマル": rows_a, "ファッション": rows_b}
    sheet = mocker.Mock()

    creator = mocker.Mock()
    creator.create_plan.side_effect = [
        {"inboundPlanId": "wfA", "link": "url-A"},
        {"inboundPlanId": "wfB", "link": "url-B"},
    ]
    creator.get_packing_groups.side_effect = [
        [{"packingGroupId": "pg-a", "items": [{"msku": "A_1"}]}],
        [
            {"packingGroupId": "pg-b1", "items": [{"msku": "B_1"}]},
            {"packingGroupId": "pg-b2", "items": [{"msku": "B_2"}]},
        ],
    ]

    with pytest.raises(RuntimeError, match=r"1グループ"):
        _check_fc_split_for_all_groups(groups, creator, sheet)

    sheet.write_trial_plan_url.assert_not_called()
    captured = capsys.readouterr()
    out = captured.err + captured.out
    assert "ファッション" in out
    # ノーマルは分割していないので明示的に[ノーマル]の試作プラン報告は出ない (OKなので報告対象外)
```

- [ ] **Step 2: Run test to verify it passes**

```bash
PYTHONPATH=src python3 -m pytest tests/usecases/test_batch_labels_fc_split.py::test_check_fc_split_partial_split_blocks_all_writes -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add python/tests/usecases/test_batch_labels_fc_split.py
git commit -m "$(cat <<'EOF'
test(batch-labels): 一部グループのみ分割した場合のall-or-nothing動作を検証

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `PurchaseSheet.write_trial_plan_url()` 追加

**Files:**
- Modify: `python/src/infrastructure/spreadsheet/purchase_sheet.py`
- Test: `python/tests/infrastructure/spreadsheet/test_purchase_sheet_trial_plan_url.py` (新規)

FC分割pre-check 用に「納品プラン」列にだけ書き込む新メソッド (既存 `write_plan_result` は「発送日」も書いてしまうため別メソッド)。

- [ ] **Step 1: Check existing test infrastructure**

`python/tests/infrastructure/spreadsheet/` の構造を確認:

```bash
ls python/tests/infrastructure/spreadsheet/ 2>&1 || echo "directory missing"
```

ディレクトリがなければ作成し、`__init__.py` を作成:

```bash
mkdir -p python/tests/infrastructure/spreadsheet
touch python/tests/infrastructure/spreadsheet/__init__.py
```

- [ ] **Step 2: Write the failing test**

`python/tests/infrastructure/spreadsheet/test_purchase_sheet_trial_plan_url.py` を新規作成:

```python
"""PurchaseSheet.write_trial_plan_url のテスト"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest
from src.infrastructure.spreadsheet.purchase_sheet import PurchaseSheet


def test_write_trial_plan_url_writes_hyperlink_to_each_row(mocker):
    """指定された rows の「納品プラン」列に HYPERLINK 数式を書き込む"""
    sheet = mocker.Mock(spec=PurchaseSheet)
    sheet.write_trial_plan_url = PurchaseSheet.write_trial_plan_url.__get__(sheet)
    sheet._get_column_index_by_name = mocker.Mock(return_value=20)  # 21列目 (1-indexed)
    sheet.write_formula = mocker.Mock()

    rows = [
        SimpleNamespace(row_number=340),
        SimpleNamespace(row_number=341),
    ]
    url = "https://sellercentral.amazon.co.jp/fba/sendtoamazon/confirm_content_step?wf=wf999"
    plan_id = "wf999XYZ"

    sheet.write_trial_plan_url(rows, url, plan_id)

    assert sheet.write_formula.call_count == 2
    # 1件目: row 340, col 21, formula contains url and plan_id短縮形
    args_1 = sheet.write_formula.call_args_list[0].args
    assert args_1[0] == 340
    assert args_1[1] == 21  # plan_col = index + 1
    assert "wf999" in args_1[2]
    assert "HYPERLINK" in args_1[2]
```

- [ ] **Step 3: Run test to verify it fails**

```bash
PYTHONPATH=src python3 -m pytest tests/infrastructure/spreadsheet/test_purchase_sheet_trial_plan_url.py -v
```
Expected: FAIL with `AttributeError: ... 'write_trial_plan_url'`

- [ ] **Step 4: Write minimal implementation**

`python/src/infrastructure/spreadsheet/purchase_sheet.py` の `write_plan_result()` (43-57行) の**直後**に追加:

```python
    def write_trial_plan_url(self, rows: list[Any], url: str, plan_id: str) -> None:
        plan_col = self._get_column_index_by_name("納品プラン") + 1
        display = plan_id[:10] if plan_id else "trial"
        formula = f'=HYPERLINK("{url}","{display}")'
        for row in rows:
            self.write_formula(row.row_number, plan_col, formula)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
PYTHONPATH=src python3 -m pytest tests/infrastructure/spreadsheet/test_purchase_sheet_trial_plan_url.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python/src/infrastructure/spreadsheet/purchase_sheet.py python/tests/infrastructure/spreadsheet/
git commit -m "$(cat <<'EOF'
feat(sheet): PurchaseSheet.write_trial_plan_url() を追加

FC分割pre-check 用に「納品プラン」列にだけ HYPERLINK 数式を書き込む。
既存 write_plan_result は「発送日」も書くため別メソッドで分離。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `batch_print_labels()` に FC分割チェックを組み込み

**Files:**
- Modify: `python/src/usecases/batch_print_labels.py:25-49` (`batch_print_labels` 関数本体)

`_validate_no_blank_sku()` 直後に `_check_fc_split_for_all_groups()` を呼び出すよう変更。

- [ ] **Step 1: Write integration test**

`python/tests/usecases/test_batch_labels_fc_split.py` の末尾に追加:

```python
def test_batch_print_labels_invokes_fc_split_check(mocker):
    """batch_print_labels の処理順序で _check_fc_split_for_all_groups が呼ばれる"""
    from src.usecases import batch_print_labels as mod

    # SP-API auth と sheet を mock
    mocker.patch.object(mod, "get_auth_token", return_value="token")

    # PurchaseSheet を mock。filter後 1グループ分のデータが返る想定
    rows = [_row(340, "SKU_A"), _row(341, "SKU_B")]
    mock_sheet_cls = mocker.patch.object(mod, "PurchaseSheet")
    mock_sheet = mock_sheet_cls.return_value
    mock_sheet.data = rows

    # SalesSheet も mock
    mock_sales_cls = mocker.patch("src.infrastructure.spreadsheet.sales_sheet.SalesSheet")
    mock_sales_cls.return_value.load_asin_to_sku_fnsku.return_value = {}

    # InboundPlanCreator を mock (FC分割なし)
    mock_creator_cls = mocker.patch.object(mod, "InboundPlanCreator")
    mock_creator_cls.return_value.create_plan.return_value = {
        "inboundPlanId": "wfX", "link": "url-X"
    }
    mock_creator_cls.return_value.get_packing_groups.return_value = [{"packingGroupId": "pg-x"}]

    # ラベル生成以降は実行しないように short-circuit
    mocker.patch.object(mod, "_create_label_pdf", return_value=[])
    mocker.patch.object(mod, "_create_instruction_sheet", return_value=Path("/tmp/dummy.xlsx"))
    mocker.patch.object(mod, "_create_inspection_sheet", return_value=None)
    mocker.patch.object(mod, "_write_to_sheet")
    mocker.patch.object(mod, "_send_chatwork_by_group")
    mocker.patch.object(mod, "_print_summary")

    config = mocker.Mock()
    config.chatwork_api_token = None
    config.chatwork_room_id = None
    repo = mocker.Mock()

    mod.batch_print_labels(config, repo, category_filter=["ノーマル"])

    # FC分割チェックが create_plan を呼んだことを確認
    mock_creator_cls.return_value.create_plan.assert_called_once()
    mock_creator_cls.return_value.get_packing_groups.assert_called_once()
    # OK だったので write_trial_plan_url が呼ばれる
    mock_sheet.write_trial_plan_url.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=src python3 -m pytest tests/usecases/test_batch_labels_fc_split.py::test_batch_print_labels_invokes_fc_split_check -v
```
Expected: FAIL (FC分割チェックがまだ batch_print_labels から呼ばれていない)

- [ ] **Step 3: Wire into batch_print_labels()**

`python/src/usecases/batch_print_labels.py` の `batch_print_labels()` 関数本体を編集。

**変更前 (54-58行付近)**:
```python
    from infrastructure.spreadsheet.sales_sheet import SalesSheet
    sales = SalesSheet(repo)
    asin_map = sales.load_asin_to_sku_fnsku()
    sheet.fill_missing_sku_fnsku_from_sales(asin_map)
    _validate_no_blank_sku(sheet.data)

    click.echo(f"\n{len(non_home_groups)}グループを処理します")
```

**変更後**:
```python
    from infrastructure.spreadsheet.sales_sheet import SalesSheet
    sales = SalesSheet(repo)
    asin_map = sales.load_asin_to_sku_fnsku()
    sheet.fill_missing_sku_fnsku_from_sales(asin_map)
    _validate_no_blank_sku(sheet.data)

    click.echo("\n[FC分割pre-check] 試作プランを作成して packingGroups を確認...")
    creator = InboundPlanCreator(auth_token=access_token)
    _check_fc_split_for_all_groups(non_home_groups, creator, sheet)

    click.echo(f"\n{len(non_home_groups)}グループを処理します")
```

ファイル上部の import に `InboundPlanCreator` を追加:
```python
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
```

- [ ] **Step 4: Run test to verify it passes**

```bash
PYTHONPATH=src python3 -m pytest tests/usecases/test_batch_labels_fc_split.py -v
```
Expected: 全 PASS (Task 2/3/4 のテスト + 新規 integration test)

- [ ] **Step 5: Run full test suite for regression check**

```bash
PYTHONPATH=src python3 -m pytest -v 2>&1 | tail -40
```
Expected: 全 PASS (既存テストへの影響なし)

既存の `test_batch_labels_*.py` が落ちる場合は SP-API mock の追加が必要。落ちたケース名を確認し、`InboundPlanCreator` を mock するか、test fixture で bypass する。

- [ ] **Step 6: Commit**

```bash
git add python/src/usecases/batch_print_labels.py python/tests/usecases/test_batch_labels_fc_split.py
git commit -m "$(cat <<'EOF'
feat(batch-labels): FC分割pre-checkをbatch_print_labelsに組み込み

SKU/FNSKU validation 直後に試作プランを作成して packingGroups を確認。
分割があればラベル生成前に停止、無ければ「納品プラン」列に URL 書き込み。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: ドキュメント更新

**Files:**
- Modify: `procurements/management-helper/.claude/commands/batch-labels.md`
- Modify: `procurements/fullfilment/.claude/commands/update-fulfillment.md`

- [ ] **Step 1: Update batch-labels.md**

`procurements/management-helper/.claude/commands/batch-labels.md` の「事前確認: FC 分割」セクション (10-60行) を以下に置き換え:

```markdown
## 事前確認: FC 分割 (自動化済み)

`/batch-labels` は実行時に各グループで SP-API 試作プランを作成し、`packingGroups` を取得して FC 分割を事前検知する。

### 自動的な動作

- **1 packingGroup (分割なし)**: 「納品プラン」列に試作プラン URL を `=HYPERLINK(...)` で書き込み、そのままラベル生成・指示書作成・Chatwork送信に進む。後段 `/update-fulfillment` でこの試作プランが再利用される。
- **2+ packingGroups (分割あり)**: 全グループ走査後に RuntimeError で停止。各 SKU の振り分けを表示。ラベルPDF・指示書・Chatwork送信は一切実行されない (all-or-nothing 方針)。

### 分割検知時のメッセージ例

```
⚠️ FC分割を検知しました。

[ノーマル] 試作プラン: wf52345... (2グループに分割)
  グループ1 (pg-aaa): 行340, 352, 353 (3 SKUs)
  グループ2 (pg-bbb): 行357, 359, 360 (3 SKUs)
  プランURL: https://sellercentral.amazon.co.jp/fba/sendtoamazon/confirm_content_step?wf=wf52345...

RuntimeError: FC分割を検知 (1グループ)。仕入管理シートの「納品分類」列をグループ別に書き換えてから再実行してください。
```

### 分割時の対処

1. 表示された SKU/行番号に従って、仕入管理シートの「納品分類」列をグループ別に書き換え (例: `ノーマル` → `ノーマル1` / `ノーマル2`)
2. `/batch-labels --categories "ノーマル1,ノーマル2"` で再実行
3. 古い試作プランは Seller Central で手動削除 (SP-API `cancelInboundPlan` は未実装)
```

- [ ] **Step 2: Update update-fulfillment.md**

`procurements/fullfilment/.claude/commands/update-fulfillment.md` の Step 4 (「既存プランIDチェック」のセクション) のコメントを更新:

**該当箇所 (30-34行付近)**:
```markdown
4. **既存プランIDチェック** (`SheetsFulfillmentRepository.fetch_existing_plan_id`):
   - 仕入管理シートの「納品プラン」列 (該当 plan_name 行) に既に `wf...` 形式の plan_id がある (HYPERLINK or 平文) → **既存プランを再利用** (新規 SP-API 呼び出しをスキップ)
   - 無ければ次へ
```

→

```markdown
4. **既存プランIDチェック** (`SheetsFulfillmentRepository.fetch_existing_plan_id`):
   - 仕入管理シートの「納品プラン」列 (該当 plan_name 行) に既に `wf...` 形式の plan_id がある (HYPERLINK or 平文) → **既存プランを再利用** (新規 SP-API 呼び出しをスキップ)
   - 無ければ次へ
   - **batch-labels連携運用 (標準)**: `/batch-labels` は内部で試作プランを作成し、分割なしなら「納品プラン」列に URL を書き込むため、ここでほぼ確実に再利用される。/update-fulfillment が新規プランを作成するのは batch-labels をスキップした場合のみ。
```

- [ ] **Step 3: Commit**

```bash
git add procurements/management-helper/.claude/commands/batch-labels.md procurements/fullfilment/.claude/commands/update-fulfillment.md
git commit -m "$(cat <<'EOF'
docs(batch-labels): FC分割pre-check自動化を反映、update-fulfillment連携を明記

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: バージョン bump + 動作確認

**Files:**
- Modify: `python/pyproject.toml`

新機能追加なのでマイナーバージョンアップ。`0.6.0` → `0.7.0`。

- [ ] **Step 1: Update pyproject.toml**

`python/pyproject.toml` の version 行を編集:

**変更前**:
```toml
version = "0.6.0"
```

**変更後**:
```toml
version = "0.7.0"
```

- [ ] **Step 2: Run full test suite once more**

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/management-helper/python
PYTHONPATH=src python3 -m pytest -v 2>&1 | tail -30
```
Expected: 全 PASS

- [ ] **Step 3: Dry-run by checking imports**

機能の手動動作確認はリスクが高い (実際に SP-API 試作プランを作成してしまう) ため、import 確認のみ:

```bash
PYTHONPATH=src python3 -c "
from src.usecases.batch_print_labels import _check_fc_split_for_all_groups, _build_items_from_rows, _format_split_report
from src.infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from src.infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
print('imports OK')
print('  - _check_fc_split_for_all_groups')
print('  - _build_items_from_rows')
print('  - _format_split_report')
print('  - InboundPlanCreator.get_packing_groups:', hasattr(InboundPlanCreator, 'get_packing_groups'))
print('  - PurchaseSheet.write_trial_plan_url:', hasattr(PurchaseSheet, 'write_trial_plan_url'))
"
```
Expected: `imports OK` と全項目 True

- [ ] **Step 4: Commit version bump**

```bash
git add python/pyproject.toml
git commit -m "$(cat <<'EOF'
chore: bump version to 0.7.0 (FC分割pre-check機能追加)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 完了基準

- [ ] 全テスト PASS (新規 7-8件 + 既存テストへの regression なし)
- [ ] `InboundPlanCreator.get_packing_groups()` 実装済み
- [ ] `_check_fc_split_for_all_groups()` 実装済み
- [ ] `PurchaseSheet.write_trial_plan_url()` 実装済み
- [ ] `batch_print_labels()` から FC分割チェックが呼ばれている
- [ ] ドキュメント (batch-labels.md, update-fulfillment.md) 更新済み
- [ ] バージョン `0.7.0` に bump
- [ ] 各タスクで個別 commit (TDD + 頻繁な commit)

## Self-Review チェック

- ✅ Spec の各要件にタスクが対応している (get_packing_groups: Task1, _check_fc_split: Task2-4, sheet書き込み: Task5, wiring: Task6, ドキュメント: Task7, version: Task8)
- ✅ プレースホルダなし (TODO/TBD/etc は実装手順に含まれない)
- ✅ 型・メソッド名一貫 (`get_packing_groups`, `_check_fc_split_for_all_groups`, `write_trial_plan_url`, `_build_items_from_rows`, `_format_split_report`)
- ✅ 各ステップに具体的なコードと実行コマンド付き
