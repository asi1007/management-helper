# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Google Apps Script（GAS）を使用した仕入管理とラベル印刷の自動化ツール。Amazon SP-APIとKeepa APIを連携し、ラベルPDFダウンロード、SKU数量集計、注文指示書作成、納品プラン作成を自動化する。

## 開発コマンド

```bash
# デプロイ（Google Apps Scriptへプッシュ）
clasp push

# ログイン（初回のみ）
clasp login

# ローカルに最新をプル
clasp pull
```

## 主要な実行関数（GASエディタまたはトリガーから実行）

| 関数名 | 用途 | ファイル |
|--------|------|----------|
| `generateLabelsAndInstructions()` | ラベルPDFと指示書の生成 | printLabels.js |
| `createInboundPlanFromActiveRows()` | 仕入管理シートから納品プラン作成 | inboundPlan.js |
| `createInboundPlanFromHomeShipmentSheet()` | 自宅発送シートから納品プラン作成 | homeShipment.js |
| `recordWorkStatus()` | 作業記録の追加 | workRecord.js |
| `createInspectionSheetWithTrigger()` | 検品シート作成（フォーム送信トリガー） | createInspectionSheet.js |
| `updateInventoryEstimateFromStockSheet()` | 在庫推測値の更新 | updateInventoryEstimateFromStock.js |

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
│   ├── amazon/services.js    # Amazon SP-API連携（ラベル取得、納品プラン作成、FNSKU解決）
│   └── spreadsheet/          # Google Sheets連携
│       ├── baseSheet.js      # シート操作の基底クラス
│       ├── baseRow.js        # 行オブジェクト（配列互換、row.get('列名')対応）
│       ├── purchaseSheet.js  # 仕入管理シート
│       ├── homeShipmentSheet.js
│       ├── instructionSheet.js
│       ├── workRecordSheet.js
│       └── inspectionMasterRepo.js  # リポジトリ実装
├── usecases/         # ユースケース層（アプリケーションロジック）
└── shared/utilities.js  # 共有設定（環境変数、認証トークン）
```

## コード規約

- **型ヒント**: JSDocコメントで型情報を記載（`@param`, `@returns`）
- **docstring**: 書かない。コード自体を自己説明的にする
- **関数粒度**: SLAP原則（Single Level of Abstraction Principle）に準拠
- **外部依存**: `IInspectionMasterRepository`のようにインターフェースで抽象化

## 重要な設計パターン

### BaseSheet / BaseRow パターン
スプレッドシートの列名を抽象化し、列の追加・削除に強い設計：
```javascript
const sheet = new PurchaseSheet('仕入管理');
const rows = sheet.getActiveRowData();  // BaseRow[]を返す
const sku = rows[0].get('SKU');         // 列名でアクセス
```

### Amazon SP-API連携
`src/infrastructure/amazon/services.js`に集約：
- `Downloader`: ラベルPDF取得
- `InboundPlanCreator`: 納品プラン作成（Send-to-Amazon workflow）
- `FnskuGetter`: FNSKU取得
- `MerchantListingsSkuResolver`: MSKU→ASINの解決

### 環境設定
`src/shared/utilities.js`の`getConfig()`で環境変数を取得。機密情報はPropertiesServiceまたは.envから読み込み。

## 注意事項

- GAS環境はES5レベル。`let`/`const`は使用可能だが、一部のモダンJS機能は制限あり
- ファイルの読み込み順序は`.clasp.json`の`filePushOrder`で制御（utilities.jsが先頭）
- Amazon SP-APIのレート制限に注意（特に納品プラン作成時）
