# Management Helper

Google Apps Scriptを使用した仕入管理とラベル印刷の自動化ツールです。

## 機能

- Amazon SP-APIを使用したラベルPDF自動ダウンロード
- SKUの数量集計と重複管理
- 注文指示書の自動作成
- Keepa APIを使用した商品画像取得

## セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/asi1007/management-helper.git
cd management-helper
```

### 2. claspのインストール

```bash
npm install -g @google/clasp
```

### 3. 機密情報の設定

`printLabels_with_secrets.js` を参考に、以下の機密情報を `printLabels.js` に設定してください：

- `SHEET_ID`: Google SheetsのシートID
- `API_KEY`: Amazon SP-APIのAPIキー
- `API_SECRET`: Amazon SP-APIのAPIシークレット
- `REFRESH_TOKEN`: Amazon SP-APIのリフレッシュトークン
- Keepa APIキー（`getKeepaProductImage`関数内）

### 4. Google Apps Scriptにデプロイ

```bash
clasp push
```

## 使用方法

- `getData()`: 仕入管理シートからデータを取得し、ラベルPDFと指示書を生成
- `loadLabelPDFs()`: 指示書シートからラベルPDFを一括生成

## 注意事項

- `printLabels_with_secrets.js` は機密情報を含むため、リポジトリには含まれていません
- デプロイ前に必ず機密情報を設定してください
- 機密情報が漏洩した場合は、Amazon SP-APIの認証情報を再生成してください

## ライセンス

Copyright (c) 2024

