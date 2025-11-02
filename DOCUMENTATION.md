# ドキュメント

## Amazon SP-API リファレンス

### 公式ドキュメント

- [SP-API 開発者サイト](https://sell.amazon.com/developers)
- [SP-API 変更履歴](https://developer-docs.amazon.com/sp-api/lang-ja_JP/changelog)
- [SP-API 公式サイト](https://developer.amazonservices.com/ja-jp)
- [SP-API ドキュメント](https://developer-docs.amazon.com/sp-api/)

### 使用しているSP-API

#### FBA Inbound API
- **エンドポイント**: `https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20/items/labels`
- **用途**: FBAラベルPDFをダウンロード
- **認証**: LWA (Login with Amazon)
- **メソッド**: POST

**リクエストパラメータ:**
```json
{
  "labelType": "STANDARD_FORMAT",
  "marketplaceId": "A1VC38T7YXB528",
  "mskuQuantities": [
    {
      "msku": "SELLER_SKU",
      "quantity": 10
    }
  ],
  "localeCode": "ja_JP",
  "pageType": "A4_40_52x29"
}
```

**レスポンス:**
```json
{
  "documentDownloads": [
    {
      "uri": "https://...",
      "documentType": "LABEL"
    }
  ]
}
```

#### FBA Inventory API
- **エンドポイント**: `https://sellingpartnerapi-fe.amazon.com/fba/inventory/v1/summaries`
- **用途**: FNSKUを取得
- **認証**: LWA (Login with Amazon)
- **メソッド**: GET

**リクエストパラメータ:**
```
marketplaceIds=A1VC38T7YXB528
granularityType=Marketplace
granularityId=A1VC38T7YXB528
details=true
sellerSku=SELLER_SKU
```

**レスポンス:**
```json
{
  "inventorySummaries": [
    {
      "sellerSku": "SELLER_SKU",
      "fnSku": "FNSKU_CODE",
      "asin": "B0XXXXX",
      "productName": "商品名",
      "totalQuantity": 10
    }
  ]
}
```

### マーケットプレイスID

- **日本**: A1VC38T7YXB528
- **米国**: ATVPDKIKX0DER
- **英国**: A1F83G8C2ARO7P
- **ドイツ**: A1PA6795UKMFR9

### 認証方法

#### LWA (Login with Amazon)

**アクセストークンの取得:**
```javascript
function getAuthToken() {
  const url = "https://api.amazon.com/auth/o2/token";
  const payload = {
    'grant_type': 'refresh_token',
    'refresh_token': REFRESH_TOKEN,
    'client_id': API_KEY,
    'client_secret': API_SECRET
  };
  
  const options = {
    method: 'post',
    payload: payload
  };
  
  const response = UrlFetchApp.fetch(url, options);
  const json = JSON.parse(response.getContentText());
  return json.access_token;
}
```

**APIリクエスト:**
```javascript
const options = {
  method: 'get',
  muteHttpExceptions: true,
  headers: {
    "Accept": "application/json",
    "x-amz-access-token": accessToken
  }
};

const response = UrlFetchApp.fetch(apiUrl, options);
```

### エラーハンドリング

**HTTPステータスコード:**
- 200: 成功
- 400: 不正なリクエスト（パラメータエラー）
- 401: 認証エラー
- 403: 権限不足
- 404: リソースが見つからない
- 429: リクエスト制限超過
- 500: サーバーエラー

**エラーレスポンス例:**
```json
{
  "errors": [
    {
      "code": "InvalidInput",
      "message": "Invalid request, please check your input.",
      "details": ""
    }
  ]
}
```

### レート制限

SP-APIにはレート制限があります：
- 通常は1秒あたり0.5〜2リクエスト
- バースト時は1秒あたり最大数十リクエスト
- APIによって異なる

詳しくは[SP-API レート制限ドキュメント](https://developer-docs.amazon.com/sp-api/docs/rate-limits)を参照してください。

### 参考リンク

- [SP-API 入門ガイド](https://developer-docs.amazon.com/sp-api/docs/sp-api-overview)
- [認証と認可](https://developer-docs.amazon.com/sp-api/docs/authentication-and-authorization)
- [エラーハンドリング](https://developer-docs.amazon.com/sp-api/docs/troubleshooting)
- [チュートリアル](https://developer-docs.amazon.com/sp-api/docs/sp-api-tutorial)

