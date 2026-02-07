/* exported MerchantListingsSkuResolver */

/**
 * 出品レポート（GET_MERCHANT_LISTINGS_ALL_DATA）から ASIN -> seller-sku を解決する。
 * 注意: レポート生成には時間がかかる場合があるため、短時間ポーリングしてDONEにならない場合は例外にする。
 */
class MerchantListingsSkuResolver {
  constructor(authToken) {
    this.authToken = authToken;
    this.REPORTS_API_BASE = 'https://sellingpartnerapi-fe.amazon.com/reports/2021-06-30';
    this.marketplaceId = 'A1VC38T7YXB528';
  }

  /**
   * @param {string[]} asins
   * @returns {Map<string,string>} asin -> sku
   */
  resolveSkusByAsins(asins) {
    const target = Array.from(new Set((asins || []).map(a => String(a || '').trim()).filter(Boolean)));
    if (target.length === 0) return new Map();

    const reportId = this._createMerchantListingsReport();
    const docId = this._waitReportDoneAndGetDocumentId(reportId);
    const tsv = this._downloadReportDocumentText(docId);
    return this._extractAsinSkuMap(tsv, target);
  }

  _request(url, method, payloadObj = null) {
    const options = {
      method: method,
      muteHttpExceptions: true,
      headers: {
        'Accept': 'application/json',
        'x-amz-access-token': this.authToken,
        'Content-Type': 'application/json'
      }
    };
    if (payloadObj) {
      options.payload = JSON.stringify(payloadObj);
    }
    const res = UrlFetchApp.fetch(url, options);
    const status = res.getResponseCode();
    const body = res.getContentText();
    if (status < 200 || status >= 300) {
      throw new Error(`Reports API request failed (status ${status}): ${body}`);
    }
    return body ? JSON.parse(body) : {};
  }

  _createMerchantListingsReport() {
    const payload = {
      reportType: 'GET_MERCHANT_LISTINGS_ALL_DATA',
      marketplaceIds: [this.marketplaceId]
    };
    const json = this._request(`${this.REPORTS_API_BASE}/reports`, 'post', payload);
    if (!json.reportId) {
      throw new Error(`reportIdが取得できませんでした: ${JSON.stringify(json)}`);
    }
    console.log(`[SKU補完] Report created: ${json.reportId}`);
    return json.reportId;
  }

  _waitReportDoneAndGetDocumentId(reportId) {
    const timeoutMs = 90000; // 90秒
    const intervalMs = 5000;
    const start = Date.now();

    while (Date.now() - start < timeoutMs) {
      const json = this._request(`${this.REPORTS_API_BASE}/reports/${reportId}`, 'get');
      const status = json.processingStatus;
      console.log(`[SKU補完] Report status: ${status}`);
      if (status === 'DONE') {
        if (!json.reportDocumentId) {
          throw new Error(`reportDocumentIdが取得できませんでした: ${JSON.stringify(json)}`);
        }
        return json.reportDocumentId;
      }
      if (status === 'CANCELLED' || status === 'FATAL') {
        throw new Error(`レポート生成に失敗しました (status=${status}): ${JSON.stringify(json)}`);
      }
      Utilities.sleep(intervalMs);
    }
    throw new Error('レポート生成が完了していません。少し待ってから再実行してください。');
  }

  _downloadReportDocumentText(reportDocumentId) {
    const json = this._request(`${this.REPORTS_API_BASE}/documents/${reportDocumentId}`, 'get');
    if (!json.url) {
      throw new Error(`documentsのurlが取得できませんでした: ${JSON.stringify(json)}`);
    }
    const res = UrlFetchApp.fetch(json.url, { method: 'get', muteHttpExceptions: true });
    const blob = res.getBlob();
    const algo = json.compressionAlgorithm || '';

    // bytes（圧縮があれば展開）
    let bytes = blob.getBytes();
    if (algo === 'GZIP') {
      // GASはUtilities.ungzipでBlobを展開できる
      bytes = Utilities.ungzip(bytes);
    }

    // まずUTF-8で試し、ヘッダーが文字化けしてそうならShift_JISで読み直す
    const utf8 = Utilities.newBlob(bytes).getDataAsString('UTF-8');
    const sjis = Utilities.newBlob(bytes).getDataAsString('Shift_JIS');
    const looksValid = (text) => {
      const firstLine = String(text || '').split(/\r?\n/)[0] || '';
      // 英語/日本語どちらのヘッダーでも「それっぽい」語が含まれるかで判定
      return /seller-sku|item-sku|asin1|asin|出品者SKU|商品ID|商品IDタイプ/.test(firstLine);
    };
    const chosen = looksValid(utf8) ? utf8 : (looksValid(sjis) ? sjis : utf8);
    console.log(`[SKU補完] Report decoded as: ${chosen === utf8 ? 'UTF-8' : 'Shift_JIS'}`);
    return chosen;
  }

  _extractAsinSkuMap(tsvText, targetAsins) {
    const want = new Set((targetAsins || []).map(a => String(a || '').trim()).filter(Boolean));
    const result = new Map();
    if (!tsvText) return result;

    const lines = String(tsvText).split(/\r?\n/).filter(l => l !== '');
    if (lines.length === 0) return result;

    const header = lines[0]
      .split('\t')
      .map(h => String(h || '').replace(/^\uFEFF/, '').trim());

    const indexOfAny = (candidates) => {
      for (const key of candidates) {
        const idx = header.indexOf(key);
        if (idx !== -1) return idx;
      }
      return -1;
    };

    // 英語ヘッダー（公式例）: seller-sku, asin1 / asin
    // 日本語ヘッダー（文字コード/設定で変わる）: 出品者SKU, 商品ID, 商品IDタイプ
    const skuIdx = indexOfAny(['seller-sku', 'item-sku', '出品者SKU']);
    const asinIdx = indexOfAny(['asin1', 'asin', 'ASIN1', 'ASIN']);
    const productIdIdx = indexOfAny(['product-id', 'item-id', '商品ID']);
    const productIdTypeIdx = indexOfAny(['product-id-type', 'item-id-type', '商品IDタイプ']);

    if (skuIdx === -1 || (asinIdx === -1 && productIdIdx === -1)) {
      throw new Error(`出品レポートのヘッダー解析に失敗しました。header=${JSON.stringify(header)}`);
    }

    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split('\t');

      let asin = '';
      if (asinIdx !== -1) {
        asin = String(cols[asinIdx] || '').trim();
      } else {
        // 商品IDタイプがASINの行だけ商品IDをASIN扱い
        const idType = String(cols[productIdTypeIdx] || '').trim().toUpperCase();
        const idVal = String(cols[productIdIdx] || '').trim();
        if (idType === 'ASIN' || (/^[A-Z0-9]{10}$/.test(idVal) && !idType)) {
          asin = idVal;
        }
      }
      if (!asin || !want.has(asin)) continue;
      const sku = String(cols[skuIdx] || '').trim();
      if (!sku) continue;
      if (!result.has(asin)) {
        result.set(asin, sku);
      }
      if (result.size >= want.size) break;
    }

    console.log(`[SKU補完] Resolved ${result.size}/${want.size} ASINs`);
    return result;
  }
}
