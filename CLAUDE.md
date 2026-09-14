# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Google Apps Script（GAS）を使用した仕入管理とラベル印刷の自動化ツール。Amazon SP-APIとKeepa APIを連携し、ラベルPDFダウンロード、SKU数量集計、注文指示書作成、納品プラン作成、在庫推測値管理を自動化する。

## 開発コマンド

```bash
# デプロイ（Google Apps Scriptへプッシュ）
clasp push

# ローカルに最新をプル
clasp pull

# ログイン（初回のみ）
clasp login
```

テストフレームワークは未導入。GASエディタ上またはトリガーから手動実行して動作確認する。

## 主要な実行関数（GASエディタまたはトリガーから実行）

| 関数名 | 用途 | ファイル |
|--------|------|----------|
| `generateLabelsAndInstructions()` | ラベルPDFと指示書の生成 | printLabels.js |
| `createInboundPlanFromActiveRows()` | 仕入管理シートから納品プラン作成 | inboundPlan.js |
| `createInboundPlanFromActiveRowsWithPlacementSelection()` | 納品プラン作成（Placement Option選択UI付き） | inboundPlan.js |
| `createInboundPlanFromHomeShipmentSheet()` | 自宅発送シートから納品プラン作成 | homeShipment.js |
| `recordWorkStart()` / `recordWorkEnd()` | 作業記録（開始・終了） | workRecord.js |
| `recordDefect()` | 不良品登録（購入数減算＋作業記録追記） | workRecord.js |
| `createInspectionSheetWithTrigger()` | 検品シート作成（フォーム送信トリガー） | createInspectionSheet.js |
| `updateInventoryEstimateFromStockSheet()` | 在庫推測値の更新 | updateInventoryEstimateFromStock.js |
| `updateStatusEstimateFromInboundPlans()` | ステータス推測値の更新 | updateStatusEstimate.js |
| `splitRow()` | 行分割（納品数入力） | splitRow.js |
| `updateArrivalDate()` | 自宅到着日更新 | updateArrivalDate.js |
| `chfilter()` | フィルタ設定 | setfilter.js |

## アーキテクチャ

DDDに基づく3層構造：

```
src/
├── domain/           # ドメイン層（ビジネスロジック）
│   ├── label/        # ラベル管理ドメイン
│   │   ├── entities/LabelItem.js         # ラベル品目エンティティ
│   │   └── services/LabelAggregator.js   # SKU集計サービス
│   └── inspection/   # 検品ドメイン
│       ├── entities/InspectionMasterItem.js
│       ├── repositories/IInspectionMasterRepository.js  # インターフェース
│       └── value_objects/InspectionMasterCatalog.js
├── infrastructure/   # インフラストラクチャ層（外部システム連携）
│   ├── amazon/       # Amazon SP-API連携（4ファイルに分割）
│   │   ├── downloader.js                 # ラベルPDFダウンロード
│   │   ├── fnskuGetter.js                # SKU→FNSKU解決
│   │   ├── inboundPlanCreator.js         # 納品プラン作成・Placement Option管理
│   │   └── merchantListingsSkuResolver.js # ASIN→SKU解決（出品レポート利用）
│   └── spreadsheet/  # Google Sheets連携
│       ├── baseSheet.js      # シート操作の基底クラス
│       ├── baseRow.js        # 行オブジェクト（配列互換、row.get('列名')対応）
│       ├── purchaseSheet.js  # 仕入管理シート
│       ├── homeShipmentSheet.js
│       ├── instructionSheet.js
│       ├── workRecordSheet.js
│       └── inspectionMasterRepo.js  # リポジトリ実装
├── usecases/         # ユースケース層（アプリケーションロジック）
└── shared/utilities.js  # 共有設定（環境変数、認証トークン、SettingSheet）
```

## コード規約

- **型ヒント**: JSDocコメントで型情報を記載（`@param`, `@returns`）
- **docstring**: 書かない。コード自体を自己説明的にする
- **関数粒度**: SLAP原則（Single Level of Abstraction Principle）に準拠
- **外部依存**: `IInspectionMasterRepository`のようにインターフェースで抽象化
- **クラス公開**: `/* exported ClassName */`コメントでGAS環境へのクラス公開を宣言

## 重要な設計パターン

### BaseSheet / BaseRow パターン
スプレッドシートの列名を抽象化し、列の追加・削除に強い設計：
```javascript
const sheet = new PurchaseSheet('仕入管理');
const rows = sheet.getActiveRowData();  // BaseRow[]を返す
const sku = rows[0].get('SKU');         // 列名でアクセス（自動trim付き）
const value = rows[0][5];              // 配列互換アクセスも可能
// rows[0].rowNumber で実シート上の行番号を取得可能
```

### Amazon SP-API連携
`src/infrastructure/amazon/`に4ファイルで責務分離：
- `Downloader`: ラベルPDF取得
- `InboundPlanCreator`: 納品プラン作成（Send-to-Amazon workflow、prepOwner自動リトライ、Placement Option生成・選択・確定）
- `FnskuGetter`: SKU→FNSKU取得
- `MerchantListingsSkuResolver`: ASIN→SKU解決（出品レポートAPI利用、UTF-8/Shift_JIS自動判定）

### 環境設定
`src/shared/utilities.js`の`getEnvConfig()`/`getConfigSettingAndToken()`で環境変数を取得。機密情報はPropertiesServiceまたは.envから読み込み。

## 主要なデータフロー

### ラベル生成フロー (`generateLabelsAndInstructions()`)
仕入管理シートの選択行 → SKU/FNSKU補完（SP-API） → SKU集計（LabelAggregator） → ラベルPDFダウンロード → 指示書作成（テンプレートコピー＋Keepa画像）→ リンクをシートに書き戻し

### ステータス推測値の更新フロー
- `updateStatusEstimateFromInboundPlans()`: ステータス「納品中」の行に対し、shipmentStatusがCLOSEDなら「在庫あり」、quantityShipped/Receivedの差が10%以下なら「在庫あり」、それ以外は「納品中」をCW列に書き込み（SKU単位で集計）
- `updateInventoryEstimateFromStockSheet()`: ステータス「在庫あり」の行に対し、stockシートのASIN別販売可能在庫から在庫数推測値をmin計算。在庫0なら「在庫無し」に更新

> **注意**: 上記2つはGAS版の記述。**現行の定期運用は Python版 (`python/main.py` を launchd から実行)** であり、状態列は書き込まない。挙動は下記「仕入管理シート『状態』列の運用ルール」を正とする。

## 仕入管理シート「状態」列の運用ルール

### 状態列（N列）は数式。絶対に書き込まない

**「状態」は手入力の列ではなく、他の列から導出される `ifs` 数式**である。値を書き込むと数式が壊れ、以降その行の状態が更新されなくなる。これが「自動処理は状態列を書かない（A方針）」の実質的な理由。

```
=ifs(
  R>0,                      "在庫あり",
  and(not(isblank(R)),R=0), "在庫なし",
  isblank(H),               "未発送",
  isblank(I),               "梱包依頼必要",
  U="自宅",                  "自宅発送",
  isblank(J),               "梱包依頼済み",
  isblank(J),               "発送依頼済み",   ← 到達不能（上と同条件のバグ）
  isblank(K),               "発送済み",
  TRUE,                     ""
)
```

| 参照列 | ヘッダー名 |
|---|---|
| H | 到着日 |
| I | 梱包依頼日 |
| J | 発送日 |
| K | 受領日 |
| R | 在庫数 |
| U | 納品分類 |

### ここから読み取れる重要な性質

- **`ifs` は上から順に評価される**ため、`在庫数` が入った瞬間に他の条件を問わず `在庫あり` になる。逆に `在庫数` が空のうちは、より上流の空欄が状態を決める。
- **`自宅発送` は `発送済み` より先に判定される**。`納品分類 = 自宅` の行は、発送日・受領日が何であれ**決して `発送済み` にならない**。自宅発送を発送済みへ遷移させる想定のロジックを書いてはいけない。ただし受領されれば `在庫数` が入り `在庫あり` になるので、**在庫数・受領日の更新対象からは外さないこと**。
- **`未発送` は「まだ出荷していない」を意味しない**。`到着日(H)` が空なだけで `未発送` と表示される。FNSKU も発送日も納品プランも埋まっているのに `未発送` の行が普通に存在する。**状態列を業務上の進捗フラグとして自動処理の条件に使ってはいけない。**
- 7番目の分岐 `isblank(J),"発送依頼済み"` は6番目と同条件のため到達不能。`発送依頼済み` は事実上どの行にも出ない（数式側の要修正点）。

### 各ユースケースの対象行と書き込み先（Python版）

| ユースケース | 対象行の条件 | 書き込む列 |
|---|---|---|
| `fill_sku_fnsku_from_shipment` | **状態非依存**。`納品プラン` にshipment IDがあり `SKU`/`FNSKU` が欠けている行（v0.10.0で状態ゲートを撤去） | SKU, FNSKU |
| `update_status_estimate` | **状態非依存**（v0.11.0で状態ゲートを撤去）。`納品プラン` にshipment ID / inboundPlanID があり、状態が `在庫あり` / `在庫なし` **以外**の行。shipmentが `CLOSED` または受領率90%以上で受領とみなす | 在庫数, 受領日 |
| `update_inventory_estimate_from_stock` | 状態 ∈ `在庫あり` / `在庫なし`。stockシートの**販売可能＋受領中＋転送中＋処理中**を ASIN 別に合計し、新しい行から順に min 配分。**stockに載っていないASINは書かない** | 在庫数 |
| `archive_out_of_stock` | 状態 = `在庫なし` かつ **受領日が前月末以前**。**毎月2日 09:45** に月1回 | （行を過去仕入れログへ移動して削除） |
| `delete_blank_rows` | 「状態」列**以外**の全列が空の行 | （行削除） |

`update_status_estimate` は先頭で `fill_sku_fnsku_from_shipment` を自動実行する。

### 空白行の判定と削除（`delete-blank-rows`）

```bash
python3 main.py delete-blank-rows            # 検出のみ（dry-run）
python3 main.py delete-blank-rows --execute  # 実削除
```

**判定ロジック: 「状態」列を除く全列が空なら空白行。**

状態列を判定から外すのが要点。状態は数式で、中身が空の行でも `isblank(到着日)` により必ず `未発送` を返すため、**状態を条件に含めると空白行は永久に検出できない**（`TARGET_STATUSES` のデッドロックと同じ罠）。除外対象は `FORMULA_COLUMNS` 定数で管理し、他に数式列を追加したらここにも足すこと。

削除は **行番号の降順** で `deleteDimension`。昇順で消すと後続のインデックスがずれる。状態列の数式は相対参照なので、行削除後も各行が自分の行を参照した状態が保たれる（削除後に検証済み）。

launchd には登録していない（不可逆操作のため手動実行）。

### 既知の落とし穴

- **状態ゲートによる自己ロック**（解消済み）: かつて `fill_sku_fnsku_from_shipment` / `update_status_estimate` は状態列でフィルタしていた。しかし状態は `到着日` 等の空欄で `未発送` になるため、**「未発送 → 対象外 → 在庫数が入らない → 在庫数が空なので状態が変わらない」というデッドロック**が成立し、納品プランも発送日もある行の SKU/FNSKU・在庫数・受領日が永久に入らなかった。前者を v0.10.0、後者を v0.11.0 で状態非依存化して解消。**状態は自分たちが書く列から導出される数式なので、状態を入力条件にすると容易に循環する。今後 `状態` でフィルタする処理を足さないこと。**
- **在庫の根拠を「販売可能」だけにしない**（2026-09-10 に解消）: `update_inventory_estimate_from_stock` は
  `販売可能(fulfillableQuantity)` のみを見ていた。**納品を受領した直後の在庫は `受領中(inboundReceivingQuantity)`
  に滞留し、販売可能には入らない。** 元在庫がほぼ空のASINが大量入庫すると available が丸ごと 0 になり、
  在庫数を 0 で上書き → 状態が `在庫なし` → アーカイブが行ごと削除、という連鎖が起きる。
  実例: [B0DHTN6C5P](https://www.amazon.co.jp/dp/B0DHTN6C5P) は 08/12 の残 9個 に対し 08/13 に **2,936個** を受領。
  在庫レジャー上は 2,945個あったが、08-14 09:30 に 2行とも 0 と判定され 09:45 に削除された。
  同じ実行の 112行中 106行は正常だったので stock の読み込み失敗ではない。**同日に受領した16ASINのうち、
  全行が0になったのは元在庫が枯れていたこのASINだけ**だった。以後、在庫あり/在庫なしの行が消えたことで
  上記「状態ゲートによる自己ロック」が成立し、**約1ヶ月間 2,100個超が売上/日に反映されなかった**。
  対策は `STOCK_QUANTITY_COLUMNS = ("販売可能", "受領中", "転送中", "処理中")`。ここから列を減らさないこと。
  **`注文確保` は入れない**（客の注文が付いていて出荷されるため）。**`予約済合計` も使わない**
  （= 注文確保 + 転送中 + 処理中 なので二重計上になる）。在庫が全量 `処理中` に入って
  `販売可能` も `受領中` も 0 になる状態は実在する（2026-09-10 時点で B0DWGQSM59）。
- **FBA在庫が行に収まらないときは Todoist へ出す**: 実FBA在庫が仕入管理のロット行に配分
  しきれない＝受け皿の行が消えた合図。無音だと気づけないので毎回タスクを作る
  （`StockShortfallNotifier`。`TODOIST_API_TOKEN` 未設定なら WARNING だけ出して続行）。
  **Todoist のクライアントは他5リポジトリにも写経されている。** 共有ライブラリ `shared/` は
  venv 前提で、このリポジトリは launchd の system python で動くため import できない。
  エンドポイントは `tests/infrastructure/test_stock_shortfall_notifier.py` で固定して
  ずれを検知する（v2 は 2026-04 に廃止され 410 を返す）。
- **stock に無いASINへ 0 を書かない**: `asin_to_stock.get(asin, 0)` は「在庫0」ではなく「情報が無い」を
  0 に潰していた。現在は該当ASINをスキップし WARNING を出す。合わせて**全ASINの在庫が0なら
  `StockUnavailableError` で中断**する（stock は 納品状況 の `IMPORTRANGE` で、`#REF!` や読み込み中に
  なることが実際にある。2026-09-09 18:30 に発生）。
- **アーカイブは月1回・前月分だけ**（2026-09-10 変更）: 以前は1日4回走り、**在庫数が0になった12〜15分後には
  行が消えていた**ため、一時的な誤判定を自己修復する余地が無かった。2026-08-31 18:33 の一斉ゼロ化では
  18:45 に **121行**が削除されている（`MAX_ARCHIVE_ROWS=20` はその翌日に追加した）。現在は
  `com.wada.archive-out-of-stock` が**毎月2日 09:45** に、**受領日が前月末以前**の `在庫なし` 行だけを移す。
  受領日はシリアル値なので `get_all_values()`（表示文字列）では年が落ちる。**必ず
  `value_render_option="UNFORMATTED_VALUE"` で読むこと。**
- **`在庫あり` 行の在庫数を `update_status_estimate` で上書きしない**: `在庫あり` 以降の在庫数は stockシート基準（`update_inventory_estimate_from_stock`）が正。受領数で上書きすると実在庫と乖離する。

### 不良品登録フロー (`recordDefect()`)
自宅発送シートの選択行 → UI入力（数量・理由・コメント）→ 対応する仕入管理行の購入数を減算 → 数量0なら行削除 → 作業記録に追記

## 新商品が受領されたら Todoist へ販売開始タスク（`notify-launch-ready`）

初回仕入の在庫が FBA に受領されたら、**「◯◯ を販売開始にする」タスクを Todoist に1件**作る。
中身は **広告の出稿**と **Vine への登録**（Linear の工程6・7と同じ作業）。

| 項目 | 値 |
|---|---|
| 対象 | 仕入管理シートで **`仕入回数` = 1 かつ `受領日` が入っている**行 |
| 実行 | `com.wada.update-inventory-estimate`（**日4回**）の在庫更新の直後 |
| 通知済みの記録 | `python/.launch_ready_notified.json`（ASINの一覧） |

- **`仕入回数` 列は `auto-order` が発注時に書く。** 定義と算出方法は
  `procurements/auto-order/CLAUDE.md` の「仕入回数」を見ること。ここでは読むだけ
- **`状態` 列は条件に使わない。** 状態は自分たちが書く列から導出される数式なので、
  入力条件にすると循環する（上の「状態ゲートによる自己ロック」と同じ罠）
- **初回実行は記録だけで終わる。** 通知済みファイルが無いときは、その時点で条件を満たす
  商品を全部「通知済み」として書き込み、**タスクは作らない**。これが無いと、
  既に販売中の新商品（2026-09-14 時点で10件）にまとめてタスクが立つ
- **送信できなかった分は通知済みにしない。** `TODOIST_API_TOKEN` 未設定などで
  作られなかった商品は、設定を直した次の回に拾い直せる
- 通知済みファイルを消すと、次の実行が「初回」として再び記録だけを行う。
  作り直したいときはこれで戻せる

```bash
python3 main.py notify-launch-ready --dry-run   # 対象を表示するだけ
python3 main.py notify-launch-ready
```

## 納品分類の判定（`classify-delivery`）

新商品の「納品分類」（ノーマル / ファッション）を Amazon に実際に聞いて決め、売上/日シートへ書く。
`/register-item` の直後、ASIN が採番されてから実行する。

```bash
python3 main.py classify-delivery <ASIN>...        # --dry-run で書き込まず確認、--overwrite で再判定
```

### なぜ必要か

ファッションとノーマルを同じ納品プランに入れると **Amazon が納品先FCを分ける**。
梱包依頼（`/request-shipment`）の段階で分割が起きると、納品分類を手で書き換えて全部やり直しになる。
出品直後に分類を確定しておけば、発注時に `auto-order` が仕入管理シートへ引き継ぐので分割が起きない。

### 判定の仕組み

**カテゴリからは判定できない。** 実データでは `Automotive Parts and Accessories` と `Office Product` が
ノーマル・ファッションの両方に存在する。商品タイプでの表引きは原理的に当たらない。

そこで **試作納品プランを作って Amazon 自身に聞く**。

1. 対象SKU + ノーマル代表SKU + ファッション代表SKU の**3品・各1個**で `createInboundPlan`
2. `packingOptions` の `packingGroups` を見て、対象がどちらの代表と同居したかで分類を決める
3. `cancelInboundPlan` で試作プランを削除（確定前なので費用は発生しない）

1件あたり約12秒。**数量は1で足りる**（200個でも結果は変わらないことを実測で確認済み）。

### 代表SKUは「実績」からしか選べない（2026-08-25 の教訓）

代表SKUは `src/shared/config.py` の `DELIVERY_CATEGORY_REFERENCE_SKUS` に定数で持つ。

**売上/日シートの「納品分類」列から代表を選んではいけない。** この列には
**納品実績がなく人が予想で入れた行が混ざっている**。実際、ジュエリー袋4件（`SKU-20260806JB-01`〜`04`）は
「ファッション」と入力されていたが、判定すると**ノーマル**だった（2026-08-25 に修正）。
予想値を代表にすると代表2件が同居してしまい、判定が成立しない。

代表に使えるのは**専用FCへの納品実績があるSKU**だけ。過去の shipment を SP-API で照会した結果:

| FC | 受け入れる分類 | 代表に使えるか |
|---|---|---|
| **XJE1 / XKX4** | ノーマルのみ | ✅ ノーマル代表 |
| **TYO2 / NRT5 / QCB3** | ファッションのみ | ✅ ファッション代表 |
| QCB5 / XJE2 / XJW1 | **両方** | ❌ 判定の根拠にならない |

専用FC同士でSKUの重複は0件だった。代表を洗い直すときは、仕入管理シートの「納品プラン」列から
shipment ID を集め、`fba/inbound/v0/shipments` で `DestinationFulfillmentCenterId` と
`/shipments/{id}/items` の SKU を突き合わせる。

### 止まったときの意味

| エラー | 意味 | 対処 |
|---|---|---|
| どの代表SKUとも同居しなかった | ノーマルでもファッションでもない第3の分類の可能性 | 勝手に決めずユーザーに確認 |
| 代表SKUどうしが同じ packingGroup に入った | 代表が無効（廃番・予想値） | `DELIVERY_CATEGORY_REFERENCE_SKUS` を見直す |
| 有効なSKUが解決できない | 出品登録が終わっていない / 仮SKU (`SKU-\d{10,}`) / `#N/A` | Amazon側のSKU発行を待つ |

代表SKUが1つ無効でも、次の候補ペアへ自動でフォールバックする（最大3回）。

## GASランタイム制約

- **V8ランタイム**: `let`/`const`/`class`/`Map`/アロー関数は使用可能
- **不可**: top-level `await`、`import`/`export`構文（ESModules非対応）
- **ファイル読み込み順序**: `.clasp.json`の`filePushOrder`で制御（utilities.jsが先頭）
- **ライブラリ**: Moment.js（GASライブラリ版）、Drive API（Advanced Services）が利用可能
- **列番号管理**: SettingSheetで動的管理が原則だが、一部（CW列=101等）はハードコードされている。ヘッダーベースの列特定に移行中
- **SP-APIレート制限**: 特に納品プラン作成時はポーリング（5秒間隔、5分タイムアウト）で対応

## 共有ライブラリ（amazon_api）の解決

SP-API の認証は `automation/shared/amazon-api` に集約されている。`.env` には認証情報を持たない。

**このリポジトリは `.venv` を持たない**ので、site-packages への symlink（`link_into_venv.sh`）が使えない。
代わりに `main.py` と `tests/conftest.py` が `automation/shared/*/src` を `sys.path` に入れる。

| 実行経路 | 誰が通すか |
|---|---|
| launchd | ラッパー `ops/launchd/scripts/notify-on-failure.sh` が `PYTHONPATH` を通す |
| 手で叩く / pytest | **`main.py` と `conftest.py` が自力で解決する** |

場所は `AUTOMATION_SHARED_ROOT` があればそれ、無ければ `python/` から 3 つ上の `shared/`。
ラッパーと同じ環境変数名なので、移設するときは両方に効く。

2026-09-14、共有ライブラリ化の直後に `ModuleNotFoundError: amazon_api` で全コマンドが止まった。
launchd は動いていたが手動実行だけが落ちるので気づきにくい。**`env -u PYTHONPATH` で検証すること。**
