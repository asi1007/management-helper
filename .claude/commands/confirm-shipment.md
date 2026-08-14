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

## 注意事項

- **配送業者は必ず「その他」**。ヤマト・日本郵便（AMAZON_PARTNERED_CARRIER）を選ぶと数万円の請求が発生する。
  該当オプションが見つからなければ RuntimeError で停止する
- **梱包グループが2つ以上に分かれる案件は対象外**。`/batch-labels` の FC 分割 pre-check で
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
