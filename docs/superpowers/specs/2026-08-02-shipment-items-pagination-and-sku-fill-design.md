# 受領反映の修正: shipment items ページング対応 + SKU/FNSKU 納品ベース補完

作成日: 2026-08-02
対象: `procurements/management-helper/python`

## 背景 / 問題

「発送済み・自宅発送」なのに Amazon で受領完了しているのに、仕入管理シートの「在庫数」「受領日」が自動反映されない行が多数（在庫数空・shipment有り39件中、CLOSED=22件が取りこぼし）。

調査で判明した独立した2原因:

- **原因A（コード側バグ・主因）**: `get_shipment_items` が SP-API の NextToken ページングを処理せず、1ページ目しか読まない。複数SKU混載shipmentで行のSKUが後続ページにあると突合0となり、CLOSEDでも受領を取りこぼす。さらに v0 の NextToken は同一ページをループして返す挙動、2024版エンドポイントは403頻発かつ別データを返す不安定さがある。
  - 実証: shipment `FBA15G8F5BCV`（行64, CLOSED）は `DB-T0OT-ZDCG` を received=41 で含むが、現行コードは取得できず在庫数が空。
- **原因B（データ側）**: SKU または FNSKU が空欄の行は、そもそも突合キーが無く受領照合できない。

shipment item(v0 `ItemData`) が持つフィールド: `SellerSKU`(msku), `FulfillmentNetworkSKU`(FNSKU), `QuantityShipped`, `QuantityReceived`。**ASINは含まない**。

## ゴール

受領完了した shipment の受領数・受領日が「在庫数」「受領日」に自動反映される状態にする。SKU/FNSKU欠落行は納品(shipment)実データで補完してから照合する。

## 設計

### 修正1: `get_shipment_items` のページング対応（原因A）

`src/infrastructure/amazon/inbound_plan_creator.py`

- v0 エンドポイント (`API_BASE_V0/shipments/{id}/items` + `MarketplaceId`) を item取得の正とする。2024版はitem取得に使わない（v0が空/失敗のときのみ最終手段）。
- NextToken を辿るが以下でループを防ぐ:
  - 既出 NextToken を集合で記録し、再出現したら停止。
  - 1ページ追加して新しい `SellerSKU` が1つも増えなければ停止。
  - 安全上限（例: 50ページ）でも停止。
- 取得した item を `SellerSKU` で重複排除して集約（重複は同値なので1件保持）。
- 戻り値の形は現行と互換（`list[dict]`）。既存の `_sum_quantities_for_sku` がそのまま使える。

### 修正2: SKU/FNSKU 補完（原因B、納品ベース）

新ユースケース `src/usecases/fill_sku_fnsku_from_shipment.py`（`fill_sku_fnsku_from_shipment(config, repo)`）。

- 対象行: 状態 ∈ {発送済み, 自宅発送, 納品中} かつ 納品プラン列から shipment ID を抽出でき、SKU か FNSKU が空。
- 各shipmentの items（修正1で全SKU取得済み）から `SellerSKU ↔ FulfillmentNetworkSKU` 対応表を作る。
- 補完ルール（**既存の非空値は上書きしない**）:
  - SKUあり・FNSKU空 → SellerSKU一致itemの FNSKU を書き込む。
  - FNSKUあり・SKU空 → FulfillmentNetworkSKU一致itemの SellerSKU を書き込む。
  - 両方空:
    - shipmentのSKUが1種類のみ → その SKU/FNSKU を両方書き込む。
    - 複数種類 → シート内の他行から作る `ASIN→(SKU,FNSKU)` ローカルマップで一意に決まる場合のみ書き込む。決まらなければスキップし WARNING ログ。
- 書き込みは gspread の batch_update に集約（クォータ対策）。

### 実行順序 / 統合

- update-status の**前段**で補完を自動実行してから受領照合する（`update_status_estimate` の冒頭で `fill_sku_fnsku_from_shipment` を呼ぶ）。
- 加えて手動用に単独CLIコマンド `fill-sku-fnsku` を `main.py` に追加。
- 自動運用の論理順序: 補完 → update-status → update-inventory → archive。

### 状態列は変更しない（A方針踏襲）

補完・受領照合いずれも「状態」列は書き換えない。書き込むのは SKU / FNSKU / 在庫数 / 受領日 のみ。

## テスト（TDD）

- 修正1: フェイクhttp（またはcreatorのitems取得をモック）で、①複数ページを集約 ②NextTokenループで無限ループしない ③重複SKUが1件に集約 を検証。
- 修正2: フェイクitemsで各分岐（SKU補完 / FNSKU補完 / 単一SKU両方補完 / 複数SKU曖昧→スキップ / 非空は不変）を検証。

## スコープ外

- 「状態」列の自動更新（手動運用のまま）。
- 納品プランIDそのものが誤っている行の訂正（今回の対象は正しいID前提の取りこぼし解消＋欠落補完）。

## リスク / 留意

- v0 NextToken のループ挙動はAmazon側仕様のため、ループ検出ガードで対処。
- shipment items に ASIN が無いため、両方空かつ複数SKU混載の行はローカルマップで一意化できないとスキップ（ログで可視化）。
