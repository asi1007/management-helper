# /batch-labels FC分割 pre-check 設計

**作成日**: 2026-05-29
**対象**: `management-helper/python/src/usecases/batch_print_labels.py`
**動機**: FBA納品プラン作成時のFC分割を事前検知し、ラベル/指示書生成前に処理を停止することで、後工程 (/update-fulfillment) でのプラン分割対応コストを下げる。

## 背景

現状の `/batch-labels` は SP-API `/inbound/fba/2024-03-20/items/labels` でラベルPDFのみ生成し、納品プラン (inboundPlan) は作成しない。FC分割の判明は後段 `/update-fulfillment` で `create_plan` を呼んだ時点。分割が起きた場合、検品担当者が既にラベル+指示書で梱包作業を始めた後に「グループ別に箱を分けて」と再依頼が必要になり手戻りが大きい。

過去事例: 2026-05-17 ファッション1/2 が分割され、シートの「納品分類」列を手動で書き換えて batch-labels を再実行した。

## 方針

`/batch-labels` 実行時にラベル生成前で SP-API 試作プランを作成し、`packingGroups` の数を取得して FC 分割を検知する。分割があれば**全グループの処理を停止**し、各 SKU の振り分けを表示してユーザに「納品分類」列の書き換えを促す。

## 詳細設計

### 配置: 全グループ一括 pre-check (all-or-nothing)

```
batch_print_labels() の処理順序:
1. シートフィルタ (現状)
2. fill_missing_sku_fnsku_from_sales (現状)
3. _validate_sku_fnsku (現状)
4. ★ _check_fc_split_for_all_groups (新規)
   - 各グループで SP-API create_plan を呼ぶ
   - packingGroups の数を取得
   - いずれかのグループが 2+ → 全 SKU の振り分けを表示して RuntimeError
   - 全グループ 1 → 「納品プラン」列に試作プラン URL を書き込み、続行
5. 各グループのラベル/指示書生成 (現状)
6. Chatwork 送信 (現状)
```

**Why all-or-nothing**: グループ A だけ通って B で停止すると、A は Chatwork 送付まで進んでしまい、巻き戻しが大変。全グループ OK → 全部通す方が安全。

### 既存「納品プラン」列の扱い: 常に新規作成 (A2)

シートの「納品プラン」列に既に試作プラン URL があっても無視して新規 create_plan を呼ぶ。これにより常に最新の SKU 構成での分割確認ができる。古い試作プランはゴミとして残るが、`cancelInboundPlan` SP-API は未実装のため手動削除に依存する (現状の `/update-fulfillment` 運用と同じ)。

### 新規実装

#### 1. `InboundPlanCreator.get_packing_groups()` 追加

既存 `get_packing_group_id()` は最初の 1 件しか返さないため、リスト全体を返すメソッドを新設する。

```python
def get_packing_groups(self, inbound_plan_id: str) -> list[dict[str, Any]]:
    url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/packingGroups"
    response = httpx.get(url, headers=self._headers, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    return data.get("packingGroups", [])
```

各 packingGroup は `{"packingGroupId": "pg-...", "items": [...]}` の形 (SP-API レスポンスに準拠)。

#### 2. `_check_fc_split_for_all_groups()` ユースケース関数

```python
def _check_fc_split_for_all_groups(
    non_home_groups: dict[str, list[BaseRow]],
    access_token: str,
    sheet: PurchaseSheet,
    config: AppConfig,
) -> None:
    """各グループで試作プランを作成して FC 分割を検知。分割があれば RuntimeError"""
    creator = InboundPlanCreator(auth_token=access_token)
    split_reports: list[str] = []
    plan_urls: dict[str, str] = {}  # category -> 試作プラン URL

    for category, rows in non_home_groups.items():
        items = _build_items_from_rows(rows)  # {sku: {asin, quantity}, ...}
        try:
            result = creator.create_plan(items)
        except RuntimeError as e:
            raise RuntimeError(f"[{category}] 試作プラン作成失敗: {e}") from e

        plan_id = result["inboundPlanId"]
        plan_url = result["link"]
        plan_urls[category] = plan_url

        groups = creator.get_packing_groups(plan_id)
        if len(groups) > 1:
            sku_to_row = {str(r.get("SKU") or "").strip(): r.row_number for r in rows}
            split_reports.append(_format_split_report(category, plan_id, plan_url, groups, sku_to_row))

    if split_reports:
        click.echo("\n".join(split_reports), err=True)
        raise RuntimeError(
            f"FC分割を検知 ({len(split_reports)}グループ)。"
            "仕入管理シートの「納品分類」列をグループ別に書き換えてから再実行してください。"
        )

    # 全グループ OK → 「納品プラン」列に試作プラン URL を書き込み
    _write_plan_urls_to_sheet(sheet, non_home_groups, plan_urls)
```

#### 3. エラー時の表示形式

```
⚠️ FC分割を検知しました。「納品分類」列を書き換えてから再実行してください。

[ノーマル] 試作プラン: wf52345... (3グループに分割)
  グループ1 (pg-aaa, FC: XJE2): 行340, 352, 353, 354 (4 SKUs)
  グループ2 (pg-bbb, FC: QCB3): 行357, 359, 360, 364 (4 SKUs)
  グループ3 (pg-ccc, FC: HND8): 行377, 378, 379 (3 SKUs)

[ファッション] 試作プラン: wf52346... (2グループに分割)
  グループ1 (pg-ddd, FC: XJE2): 行336 (1 SKU)
  グループ2 (pg-eee, FC: QCB3): 行355, 374 (2 SKUs)
```

FC コードは packingGroup のレスポンスに含まれていれば表示、なければ省略。

#### 4. 「納品プラン」列書き込み

全グループ 1 packingGroup の場合、各行の「納品プラン」列に `=HYPERLINK("plan_url", "plan_id_short")` 形式で書き込む。これにより /update-fulfillment が既存プランを再利用し、SP-API の重複呼び出しを避ける。

```python
def _write_plan_urls_to_sheet(
    sheet: PurchaseSheet,
    groups: dict[str, list[BaseRow]],
    plan_urls: dict[str, str],
) -> None:
    for category, rows in groups.items():
        url = plan_urls.get(category)
        if not url:
            continue
        plan_id = _extract_plan_id_from_url(url)  # wfXXXX 抽出
        formula = f'=HYPERLINK("{url}","{plan_id[:10]}")'
        for row in rows:
            sheet.write_cell(row.row_number, "納品プラン", formula)
```

(列名「納品プラン」は既存 PurchaseSheet のヘッダーから動的解決される想定)

## テスト戦略

TDD で先に書く。pytest を使用。

### `tests/usecases/test_batch_print_labels_fc_split.py`

1. **全グループ 1 packingGroup → 続行 + 「納品プラン」列書き込み**:
   - `InboundPlanCreator.create_plan` と `get_packing_groups` を mock
   - 1 packingGroup を返す
   - 関数完了後、シートの「納品プラン」列に URL が書き込まれている

2. **1グループが 2 packingGroups → RuntimeError**:
   - 1 グループで 2 packingGroups を返す
   - RuntimeError 発生、メッセージに「FC分割を検知」を含む
   - 振り分け表示に各行番号が含まれる

3. **複数グループで分割 → 全グループの振り分け表示**:
   - グループA: 2分割、グループB: 3分割
   - RuntimeError 発生、両グループの振り分けが表示される

4. **create_plan が prepOwner エラー → リトライ後成功**:
   - 既存リトライ機構を流用、エラー伝播しない

5. **create_plan が他エラー → RuntimeError**:
   - prepOwner 以外のエラーは伝播する

### `tests/infrastructure/amazon/test_inbound_plan_creator_packing_groups.py`

1. **`get_packing_groups` 正常系**:
   - SP-API レスポンス mock で packingGroups リストを返却

2. **`get_packing_groups` 空レスポンス**:
   - `packingGroups: []` の場合、空リストを返す (例外にしない)

## SP-API コスト

各グループで1回 `POST /inboundPlans` (create_plan) + 1回 `GET /inboundPlans/{id}/packingGroups` を呼ぶ。グループ数 N に対して 2N 呼び出し。レートリミットには触れない想定 (現状の使用量から大きく増えない)。

試作プランは作成後にキャンセルしない (cancelInboundPlan 未実装)。Seller Central に残るが、/update-fulfillment が同じプランを再利用するため実害なし。

## スコープ外 (今回やらない)

- **自動シート書き換え**: 分割検知時にシートの「納品分類」列を自動書き換えする機能。誤書き換えリスクがあるため停止+表示に留める。
- **試作プランの自動 cancel**: SP-API `cancelInboundPlan` は未実装。手動削除に依存。
- **fail-fast (グループ単位停止)**: all-or-nothing 方針のため、最初のグループで分割検知しても全グループの確認を続ける。
- **既存「納品プラン」列の試作プラン再利用**: A2 を採用、常に新規作成。

## 影響範囲

| ファイル | 変更内容 |
|---|---|
| `python/src/usecases/batch_print_labels.py` | `_check_fc_split_for_all_groups()` と関連ヘルパー追加、`batch_print_labels()` から呼び出し |
| `python/src/infrastructure/amazon/inbound_plan_creator.py` | `get_packing_groups()` 追加 |
| `python/tests/usecases/test_batch_print_labels_fc_split.py` | 新規ファイル (TDD) |
| `python/tests/infrastructure/amazon/test_inbound_plan_creator_packing_groups.py` | 新規ファイル (TDD) |
| `procurements/fullfilment/.claude/commands/update-fulfillment.md` | ドキュメント更新 (batch-labels連携運用のセクション) |
| `procurements/management-helper/.claude/commands/batch-labels.md` | ドキュメント更新 (事前確認の自動化を反映) |

既存テストへの影響: `test_batch_print_labels.py` 系の既存ケースは mock 側で `_check_fc_split_for_all_groups` を bypass するか、SP-API mock を追加する必要がある。

## 成功基準

- `/batch-labels` 実行時に FC 分割なしのケースで従来通り動作する
- FC 分割があれば、ラベル/指示書生成・Chatwork 送信が一切行われずに停止する
- エラーメッセージから、どの SKU がどのグループに振り分けられたかが明確に分かる
- 全グループ OK の場合、シートの「納品プラン」列に試作プラン URL が書き込まれ、後段 /update-fulfillment で再利用される
- pytest 全グリーン
