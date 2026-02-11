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

### 不良品登録フロー (`recordDefect()`)
自宅発送シートの選択行 → UI入力（数量・理由・コメント）→ 対応する仕入管理行の購入数を減算 → 数量0なら行削除 → 作業記録に追記

## GASランタイム制約

- **V8ランタイム**: `let`/`const`/`class`/`Map`/アロー関数は使用可能
- **不可**: top-level `await`、`import`/`export`構文（ESModules非対応）
- **ファイル読み込み順序**: `.clasp.json`の`filePushOrder`で制御（utilities.jsが先頭）
- **ライブラリ**: Moment.js（GASライブラリ版）、Drive API（Advanced Services）が利用可能
- **列番号管理**: SettingSheetで動的管理が原則だが、一部（CW列=101等）はハードコードされている。ヘッダーベースの列特定に移行中
- **SP-APIレート制限**: 特に納品プラン作成時はポーリング（5秒間隔、5分タイムアウト）で対応
