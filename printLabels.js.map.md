# printLabels.js コードマップ

## 概要
Amazon FBAラベルと梱包指示書を生成するためのGoogle Apps Scriptファイル。

## 定数定義

| 定数名 | 値 | 説明 |
|--------|-----|------|
| `KEEPA_API_ENDPOINT` | `'https://api.keepa.com/product'` | Keepa APIのエンドポイントURL |
| `INSTRUCTION_SHEET_TEMPLATE_ID` | `'1YDBbEgxTnRZRqKi5UUsQAZfCgakdzVKNJtX6cPBZARA'` | 指示書シートのテンプレートID |
| `INSTRUCTION_SHEET_START_ROW` | `8` | 指示書シートのデータ開始行番号 |
| `AMAZON_IMAGE_BASE_URL` | `'https://images-na.ssl-images-amazon.com/images/I/'` | Amazon商品画像のベースURL |

## 関数一覧

### エントリーポイント

#### `generateLabelsAndInstructions()`
**行番号**: 216-268  
**説明**: ラベルと指示書を生成するメイン関数  
**処理フロー**:
1. 環境設定とシートオブジェクトの初期化
2. アクティブ行のデータ取得
3. 依頼日の書き込み
4. FNSKUの取得（空白の場合）
5. ラベルPDFの生成
6. プラン別名列への書き込み
7. 指示書の生成

**呼び出し関係**:
- → `getEnvConfig()` (config.js)
- → `SettingSheet()` (services.js)
- → `Sheet()` (services.js)
- → `getAuthToken()` (auth.js)
- → `fetchMissingFnskus()`
- → `aggregateSkusForLabels()`
- → `loadLabelPDF()`
- → `writePlanNameToRows()`
- → `makeOrderInstructionSheet()`

---

### ユーティリティ関数

#### `getKeepaProductImage(asin)`
**行番号**: 12-50  
**説明**: Keepa APIから商品画像URLを取得  
**パラメータ**:
- `asin` (string): ASINコード

**戻り値**: `string | null` - 画像URL、取得できない場合はnull

**呼び出し関係**:
- → `getEnvConfig()` (config.js)
- → `UrlFetchApp.fetch()` (GAS API)

**使用箇所**:
- `makeOrderInstructionSheet()` (76行目)

---

#### `formatDateMMDD(date)`
**行番号**: 108-114  
**説明**: 日付をMM/DD形式にフォーマット  
**パラメータ**:
- `date` (Date): 日付オブジェクト

**戻り値**: `string` - MM/DD形式の文字列

**使用箇所**:
- `writePlanNameToRows()` (198行目)

---

### データ処理関数

#### `fetchMissingFnskus(sheet, data, fnskuColumn, skuColumn, accessToken)`
**行番号**: 124-147  
**説明**: 空白のFNSKUをSP-APIから取得してシートに書き込む  
**パラメータ**:
- `sheet` (Sheet): シートオブジェクト
- `data` (Array<Array>): 行データの配列
- `fnskuColumn` (number): FNSKU列インデックス
- `skuColumn` (number): SKU列インデックス
- `accessToken` (string): アクセストークン

**呼び出し関係**:
- → `FnskuGetter()` (services.js)

**使用箇所**:
- `generateLabelsAndInstructions()` (227行目)

---

#### `aggregateSkusForLabels(data, setting)`
**行番号**: 155-181  
**説明**: SKUと数量を集約してラベル用の配列を作成  
**パラメータ**:
- `data` (Array<Array>): 行データの配列
- `setting` (SettingSheet): 設定オブジェクト

**戻り値**: `Array<Object>` - `[{msku: string, quantity: number}]`の形式の配列

**処理内容**:
1. データからSKUと数量を抽出
2. 空のSKUをフィルタリング
3. 同じSKUの数量を合算
4. オブジェクトを配列に変換

**使用箇所**:
- `generateLabelsAndInstructions()` (235行目)

---

#### `writePlanNameToRows(sheet, data, setting)`
**行番号**: 189-211  
**説明**: プラン別名列に日付と納品分類を結合した値を書き込む  
**パラメータ**:
- `sheet` (Sheet): シートオブジェクト
- `data` (Array<Array>): 行データの配列
- `setting` (SettingSheet): 設定オブジェクト

**処理内容**:
1. プラン別名列と納品分類列のインデックスを取得
2. 現在日付をMM/DD形式にフォーマット
3. 各行に「MM/DD + 納品分類」を書き込み

**呼び出し関係**:
- → `formatDateMMDD()`

**使用箇所**:
- `generateLabelsAndInstructions()` (241行目)

---

### ファイル生成関数

#### `makeOrderInstructionSheet(rows)`
**行番号**: 57-87  
**説明**: 指示書シートを作成  
**パラメータ**:
- `rows` (Array<Array>): `[[fnsku, asin, 数量, 備考, 注文依頼番号]]`の形式の配列

**戻り値**: `string` - ダウンロードURL

**処理内容**:
1. テンプレートファイルをコピー
2. 各行のデータを書き込み
3. 商品画像を取得して挿入
4. エクスポートURLを返す

**呼び出し関係**:
- → `getKeepaProductImage()`
- → `DriveApp.getFileById()` (GAS API)
- → `SpreadsheetApp.openById()` (GAS API)
- → `UrlFetchApp.fetch()` (GAS API)

**使用箇所**:
- `generateLabelsAndInstructions()` (260行目)

---

#### `loadLabelPDF(skuNums)`
**行番号**: 94-101  
**説明**: ラベルPDFを生成  
**パラメータ**:
- `skuNums` (Array<Object>): `[{msku: string, quantity: number}]`の形式の配列

**戻り値**: `string` - ラベルPDFのURL

**呼び出し関係**:
- → `getAuthToken()` (auth.js)
- → `Downloader()` (services.js)
- → `Utilities.formatDate()` (GAS API)

**使用箇所**:
- `generateLabelsAndInstructions()` (236行目)

---

## 外部依存関係

### 外部ファイル

| ファイル名 | 使用する関数/クラス | 用途 |
|-----------|-------------------|------|
| `config.js` | `getEnvConfig()` | 環境変数の取得 |
| `auth.js` | `getAuthToken()` | Amazon SP-APIのアクセストークン取得 |
| `services.js` | `Downloader` | ラベルPDFのダウンロード |
| `services.js` | `FnskuGetter` | FNSKUの取得 |
| `services.js` | `SettingSheet` | シート設定の管理 |
| `services.js` | `Sheet` | シート操作 |

### Google Apps Script API

| API | 使用箇所 | 用途 |
|-----|---------|------|
| `UrlFetchApp.fetch()` | `getKeepaProductImage()`, `makeOrderInstructionSheet()` | HTTPリクエスト |
| `DriveApp.getFileById()` | `makeOrderInstructionSheet()` | Google Driveファイル操作 |
| `SpreadsheetApp.openById()` | `makeOrderInstructionSheet()` | スプレッドシート操作 |
| `Utilities.formatDate()` | `loadLabelPDF()`, `makeOrderInstructionSheet()` | 日付フォーマット |

---

## 関数呼び出し関係図

```
generateLabelsAndInstructions() [エントリーポイント]
├── getEnvConfig() [config.js]
├── SettingSheet() [services.js]
├── Sheet() [services.js]
│   ├── getActiveRowData()
│   ├── writeRequestDate()
│   ├── writelabelURL()
│   └── writeInstructionURL()
├── getAuthToken() [auth.js]
├── fetchMissingFnskus()
│   └── FnskuGetter() [services.js]
│       └── getFnsku()
├── aggregateSkusForLabels()
│   └── setting.get()
├── loadLabelPDF()
│   ├── getAuthToken() [auth.js]
│   └── Downloader() [services.js]
│       └── downloadLabels()
├── writePlanNameToRows()
│   ├── formatDateMMDD()
│   └── setting.getOptional()
└── makeOrderInstructionSheet()
    └── getKeepaProductImage()
        ├── getEnvConfig() [config.js]
        └── UrlFetchApp.fetch() [GAS API]
```

---

## データフロー

### ラベル生成フロー

```
1. generateLabelsAndInstructions()
   ↓
2. Sheet.getActiveRowData()
   → アクティブ行のデータ取得
   ↓
3. fetchMissingFnskus()
   → 空白のFNSKUをSP-APIから取得
   ↓
4. aggregateSkusForLabels()
   → SKUと数量を集約
   ↓
5. loadLabelPDF()
   → Amazon SP-APIでラベルPDF生成
   ↓
6. Sheet.writelabelURL()
   → シートにラベルURLを書き込み
```

### 指示書生成フロー

```
1. generateLabelsAndInstructions()
   ↓
2. データを指示書形式に変換
   [fnsku, asin, 数量, 備考, 注文依頼番号]
   ↓
3. makeOrderInstructionSheet()
   ├── テンプレートをコピー
   ├── データを書き込み
   └── getKeepaProductImage()
       → 商品画像を取得して挿入
   ↓
4. Sheet.writeInstructionURL()
   → シートに指示書URLを書き込み
```

---

## エラーハンドリング

| 関数 | エラー処理 |
|------|-----------|
| `getKeepaProductImage()` | `try-catch`でエラーをキャッチし、`null`を返す |
| `makeOrderInstructionSheet()` | 空配列チェックでエラーをスロー |
| `aggregateSkusForLabels()` | 有効なSKUがない場合にエラーをスロー |
| `writePlanNameToRows()` | 設定が見つからない場合は早期リターン |
| `generateLabelsAndInstructions()` | `try-catch`でエラーをキャッチし、ログ出力後に再スロー |

---

## 設定依存

以下の設定値が`SettingSheet`から取得されます：

| 設定キー | 使用箇所 | 説明 |
|---------|---------|------|
| `"fnsku"` | `fetchMissingFnskus()`, `generateLabelsAndInstructions()` | FNSKU列のインデックス |
| `"sku"` | `fetchMissingFnskus()`, `aggregateSkusForLabels()` | SKU列のインデックス |
| `"数量"` | `aggregateSkusForLabels()`, `generateLabelsAndInstructions()` | 数量列のインデックス |
| `"asin"` | `generateLabelsAndInstructions()` | ASIN列のインデックス |
| `"備考"` | `generateLabelsAndInstructions()` | 備考列のインデックス |
| `"注文依頼番号"` | `generateLabelsAndInstructions()` | 注文依頼番号列のインデックス |
| `"依頼日"` | `Sheet.writeRequestDate()` | 依頼日列のインデックス |
| `"プラン別名"` | `writePlanNameToRows()` | プラン別名列のインデックス（オプション） |
| `"納品分類"` | `writePlanNameToRows()` | 納品分類列のインデックス（オプション） |

---

## 環境変数依存

以下の環境変数が`PropertiesService`から取得されます：

| 環境変数名 | 使用箇所 | 説明 |
|-----------|---------|------|
| `KEEPA_API_KEY` | `getKeepaProductImage()` | Keepa APIキー |
| `SHEET_ID` | `generateLabelsAndInstructions()` | スプレッドシートID |
| `PURCHASE_SHEET_NAME` | `generateLabelsAndInstructions()` | 仕入管理シート名 |

---

## 注意事項

1. **アクティブ行の選択**: `Sheet.getActiveRowData()`は複数の非連続行選択に対応しています
2. **SKU集約**: 同じSKUの数量は自動的に合算されます
3. **エラーハンドリング**: 一部のエラーは警告として処理され、処理が継続されます
4. **日付フォーマット**: 依頼日は時間部分を0に設定して書き込まれます
5. **画像取得**: Keepa APIから画像を取得できない場合は、画像なしで指示書が作成されます

