---
description: /confirm-shipment コマンド - 梱包完了報告を受けて納品プランを確定し、納品番号と輸送箱ラベルを取得する
alwaysApply: false
---

# /confirm-shipment コマンド

Chatwork で検品担当（徐雪蘭さん）から「梱包しました / 納品書をお願いします」と来た案件を、
SP-API で納品プラン確定まで進めるコマンド。

## 実行例

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/management-helper/python && \
  python3 main.py confirm-shipment --cartons "1：50*40*23 18KG" 175
```

| オプション | 既定値 | 説明 |
|---|---|---|
| `--cartons` | 必須 | 箱情報。`箱番号：L*W*H 重量KG`。複数行は `\n` 区切り（例 `1-2：60*40*32 29.1KG\n3：50*40*23 18KG`） |
| `--ship-date` | **翌日** | 出荷日 `YYYY-MM-DD` |
| `--lead-days` | 未指定 | 到着予定までの日数。**未指定なら出荷日の1ヶ月後**を自動選択 |
| `row_numbers` | 必須 | 仕入管理シートの行番号（同一納品プランの行をすべて渡す） |

## 良品数量の反映ルール（確認不要・機械的に適用する）

検品担当のメッセージには「良品数量」が SKU 単位で書かれてくる。
**以下は判断が確定しているので、ユーザーに聞かずにそのまま適用すること。**

### 1. 報告された良品数量をそのまま採用する

指示書の数量より**少なくても多くても、報告された実数を購入数に書き込む**。
実際に箱へ入っている数を納品するのが正しく、超過分を残す運用はしていない。

| 例 | 指示書 | 良品 | 登録 |
|---|---|---|---|
| 不足 | 1,000 | 987 | **987** |
| 超過 | 1,500 | 1,561 | **1,561** |

「ほかの数量は指示書の数量と合っています」と書かれていれば、**言及のない SKU は指示書のまま**。

### 2. 同一 SKU が複数行に分かれている場合は先頭行から満たす

良品数量は SKU 単位で来るが、仕入管理シートでは購入ロットごとに行が分かれていることがある。
**先頭行（行番号の小さい方）から順に指示書数量を満たし、不足分を後ろの行で吸収する。**
超過分は最後の行に上乗せする。

| 行 | 指示書 | 良品計 988 の配分 |
|---|---|---|
| 154 | 500 | **500** |
| 155 | 500 | **488** |

実装は `domain/shipment/inspection_quantity.py` の `allocate_good_quantity()`。

### 3. 箱情報が画像で来たら Read tool で読む

`[download:NNN]xxx.png` があれば必ずダウンロードして画像を読む。
箱号・件数・長・寛・高・単箱重量の表になっている。パーサに頼らず LLM が読むこと。

## 内容物申告方式は常に MANUAL_PROCESS

`setPackingInformation` の `contentInformationSource` は **常に `MANUAL_PROCESS`**
（「Amazonが手動で輸送箱の中身を処理する」）。分岐は無い。**確認不要。**

- 検品担当から来る箱情報は「箱号・件数・寸法・重量」だけで、**どの箱にどのSKUが何個入っているかは分からない**。
  箱ごとの中身を申告する `BOX_CONTENT_PROVIDED` は原理的に正しく埋められない
- 単一SKU・単一箱でも MANUAL_PROCESS で統一する（2026-08-14 ユーザー決定）。実績上、
  この方式でも手数料は ¥0 だった
- 実装は `usecases/set_packing_info.py` の `build_packing_body()`。boxes に `items` は入れない

## 出荷日と到着予定期間はユーザーに確認しない（2026-09-04 決定）

**両方とも既定値をそのまま使う。AskUserQuestion で聞かないこと。**

| 項目 | 既定 |
|---|---|
| 出荷日 | **翌日**（`--ship-date` 省略） |
| 到着予定期間 | **出荷日の1ヶ月後**（`--lead-days` 省略） |

明示の指示があるときだけオプションで上書きする（例: 空輸と分かっている便は `--lead-days 14`）。

## 到着予定期間（配送ウィンドウ）の自動設定

**既定は「出荷日の1ヶ月後」**。`domain/shipment/delivery_window_selector.py` が
Amazon の提示する配送ウィンドウ候補のうち、開始日が `出荷日 + 1ヶ月` に最も近い
`AVAILABLE` な候補を選ぶ。中国（義烏）からの海上輸送で発送日→受領日が概ね
15〜40日かかる実績に合わせたもの。

- 月末日は翌月の末日に丸める（1/31 → 2/28）
- 航空便など短納期のときだけ `--lead-days 14` のように日数で上書きする

## 処理の流れ（すべて SP-API 2024-03-20）

1. 仕入管理シートの「納品プラン」列から inboundPlanId を取得
2. `confirmPackingOption` → `setPackingInformation`（箱サイズ・重量・内容物）
3. `generatePlacementOptions` → 手数料が最小の候補を `confirmPlacementOption`
4. `generateDeliveryWindowOptions` → **出荷日+1ヶ月に最も近い候補**を `confirmDeliveryWindowOptions`
5. `generateTransportationOptions` → **「その他」(USE_YOUR_OWN_CARRIER / GROUND_SMALL_PARCEL)** を `confirmTransportationOptions`
6. 「段ボール箱数」列に箱数を書き込み、納品番号（`shipmentConfirmationId`）を出力

## 確定したら「納品プラン」列は納品番号へ置き換わる (2026-09-09)

`/request-shipment` が書くのは**試作プランID（`wf…`）**で、`/confirm-shipment` が成功すると
**納品番号（`FBA15GHML0X3`）に上書きされる**。

**これは表示の都合ではない。** `update_status_estimate` と `fill_sku_fnsku_from_shipment` は
この列から shipment ID を読むため、**`wf…` のままだと在庫数・受領日・SKU/FNSKU が永久に入らない**。

書き込む形は **`=HYPERLINK(".../fba/inbound-shipment/summary/{納品番号}", "{納品番号}")`**。
表示値は納品番号そのものなので `get_all_values()` から読む側は影響を受けない。
URL に `#` を使わない（折り返しで切れると別ページが開く）。

2026-09-09 時点で書き換えが漏れており、**68 行が `wf…` のまま**だった（`_write_shipment_confirmation_id` を追加して解消）。
過去分は placementOptions → `shipmentIds` → `getShipment` の順に辿って **61 行を復旧**した。
**`inboundPlans/{id}/shipments` は 403**（権限外）なので使えない。

`wf…` が残るのは**まだ確定していない**案件だけ。確定済みなのに `wf…` なら書き込みが失敗している。

## 既知の落とし穴

### 納品プラン列の表示値は短縮ID。フルIDは HYPERLINK 数式の中にある

「納品プラン」列は `=HYPERLINK("...confirm_content_step?wf={フルID}","{短縮ID}")` で、
**セルの表示値は `wf545a35b7` のような短縮ID**。SP-API の `inboundPlanId` は 38 文字以上必須で、
短縮IDを渡すと全エンドポイントが `InvalidInput ... Member must have length greater than or equal to 38`
の 400 を返す。

`_resolve_inbound_plan_id` は表示値がフルID形式でなければ `read_cell_formula` で数式を読み直す。
それでもフルIDが取れなければ**短縮IDのまま API を叩かずエラーで停止**する（2026-09-04 修正）。

### generate 直後の confirm は 400 を返すことがある

`generateDeliveryWindowOptions` → `confirmDeliveryWindowOptions` のように
生成直後に確定を呼ぶと、候補が `AVAILABLE` で返っていても **400 になることがある**。
数秒待って同じ ID で再送すると 202 で通る。

`InboundPlanCreator._post_with_retry` が **400 のみ 5 秒間隔で最大 3 回再試行**する（2026-09-04 追加）。
403 など他のステータスは恒久的な失敗として即座に投げる。

### 途中で落ちたら最初からやり直せない

`confirmPackingOption` / `confirmPlacementOption` は確定済みの状態で再実行すると 400 になる。
`/confirm-shipment` が途中で落ちた場合は、`get_shipment` で
`selectedDeliveryWindow` / `selectedTransportationOptionId` を見てどこまで進んだかを確認し、
**残りの工程だけを実行する**こと。

## 注意事項

- **配送業者は必ず「その他」**。ヤマト・日本郵便（AMAZON_PARTNERED_CARRIER）を選ぶと数万円の請求が発生する。
  該当オプションが見つからなければ RuntimeError で停止する
- **梱包グループが2つ以上に分かれる案件は対象外**。`/request-shipment` の FC 分割 pre-check で
  事前に分類を分けておくこと
- **輸送箱ラベルの PDF 取得は SP-API では 403**（権限外）。Seller Central UI から
  `print_labels_step?wf={planId}` を開き、ドロップダウンを **「A4版6面（99 x 105 mm）」** に
  切り替えてから「印刷」する。既定の Plain_Paper のままだと検品担当から再送依頼が来る
- 完了後は Chatwork へ納品番号・出荷日・輸送箱・ラベル PDF を送付する

## Chatwork 送付フォーマット

```
[To:986396]徐雪蘭さん
07/28ファッション2の納品ラベルです。
納品番号: FBA15GF465YJ
出荷日: 2026/8/6
輸送箱: 1箱 (50×40×23cm 18KG)
商品数量: 503個

ラベルはA4版6面です。
```
