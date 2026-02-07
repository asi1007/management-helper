/* exported FnskuGetter */

class FnskuGetter{
  constructor(authToken){
    this.authToken = authToken;
    this.LISTINGS_API_URL = "https://sellingpartnerapi-fe.amazon.com/listings/2021-08-01/items/APS8L6SC4MEPF/";
  }

  getFnsku(msku) {
    // #region agent log
    const _dbgSku = (s) => {
      const raw = String(s ?? '');
      const trim = raw.trim();
      const chars = raw.slice(0, 50).split('').map(c => c.charCodeAt(0));
      return {
        raw,
        trim,
        rawLen: raw.length,
        trimLen: trim.length,
        rawHasWhitespace: /\s/.test(raw),
        rawLeadingOrTrailingWhitespace: /^\s|\s$/.test(raw),
        rawCharCodesHead: chars
      };
    };
    try {
      console.log(`[DBG][FNSKU][getFnsku] msku=${JSON.stringify(_dbgSku(msku))}`);
    } catch (e) {}
    // #region agent log
    try{UrlFetchApp.fetch('http://127.0.0.1:7243/ingest/24045cd5-2584-4703-ab97-0442e02ed8a6',{method:'post',contentType:'application/json',payload:JSON.stringify({location:'services.js:FnskuGetter.getFnsku:entry',message:'getFnsku called',data:{mskuType:typeof msku,mskuRaw:String(msku||''),mskuTrim:String(msku||'').trim(),hasWhitespace:/\\s/.test(String(msku||'')),hasLeadingOrTrailingWhitespace:/^\\s|\\s$/.test(String(msku||''))},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'A'})});}catch(e){}
    // #endregion

    const options = {
      method: 'get',
      muteHttpExceptions: true,
      headers: {
        "Accept": "application/json",
        "x-amz-access-token": this.authToken
      }
    };

    const rawMsku = String(msku || '');
    const trimmedMsku = rawMsku.trim();
    if (!trimmedMsku) {
      console.warn('[FNSKU補完] getFnskuに空のSKUが渡されました');
      throw new Error('SKUが空のためFNSKU取得できません');
    }
    const urlRaw = `${this.LISTINGS_API_URL}${rawMsku}?marketplaceIds=A1VC38T7YXB528`;
    const urlTrim = `${this.LISTINGS_API_URL}${trimmedMsku}?marketplaceIds=A1VC38T7YXB528`;
    const urlEncoded = `${this.LISTINGS_API_URL}${encodeURIComponent(trimmedMsku)}?marketplaceIds=A1VC38T7YXB528`;

    // #region agent log
    try {
      console.log(`[DBG][FNSKU][getFnsku] urlRawHasWhitespace=${/\\s/.test(urlRaw)} urlTrimHasWhitespace=${/\\s/.test(urlTrim)} urlEncodedHasWhitespace=${/\\s/.test(urlEncoded)} urlRawPreview=${JSON.stringify(urlRaw.slice(0,180))}`);
    } catch (e) {}
    // #endregion

    // #region agent log
    try{UrlFetchApp.fetch('http://127.0.0.1:7243/ingest/24045cd5-2584-4703-ab97-0442e02ed8a6',{method:'post',contentType:'application/json',payload:JSON.stringify({location:'services.js:FnskuGetter.getFnsku:url',message:'url candidates',data:{urlRawHasWhitespace:/\\s/.test(urlRaw),urlTrimHasWhitespace:/\\s/.test(urlTrim),urlEncodedHasWhitespace:/\\s/.test(urlEncoded),urlRawPreview:urlRaw.slice(0,140),urlTrimPreview:urlTrim.slice(0,140),urlEncodedPreview:urlEncoded.slice(0,140)},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'C'})});}catch(e){}
    // #endregion

    // NOTE: SKUに空白や記号が入っても壊れないように encode + trim を使う
    const url = urlEncoded;
    let response;
    try {
      response = UrlFetchApp.fetch(url, options);
    } catch (e) {
      // #region agent log
      try {
        console.log(`[DBG][FNSKU][getFnsku] UrlFetchApp.fetch threw: name=${String(e && e.name || '')} message=${String(e && e.message || '')} url=${JSON.stringify(String(url||'').slice(0,220))}`);
      } catch (ee) {}
      try{UrlFetchApp.fetch('http://127.0.0.1:7243/ingest/24045cd5-2584-4703-ab97-0442e02ed8a6',{method:'post',contentType:'application/json',payload:JSON.stringify({location:'services.js:FnskuGetter.getFnsku:exception',message:'UrlFetchApp.fetch threw',data:{errorName:String(e && e.name || ''),errorMessage:String(e && e.message || ''),urlHasWhitespace:/\\s/.test(String(url||'')),urlPreview:String(url||'').slice(0,180)},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'E'})});}catch(ee){}
      // #endregion
      throw e;
    }

    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
    // #region agent log
    try{UrlFetchApp.fetch('http://127.0.0.1:7243/ingest/24045cd5-2584-4703-ab97-0442e02ed8a6',{method:'post',contentType:'application/json',payload:JSON.stringify({location:'services.js:FnskuGetter.getFnsku:response',message:'getFnsku response',data:{responseCode:responseCode,responseTextHead:String(responseText||'').slice(0,200)},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'D'})});}catch(e){}
    // #endregion

    if (responseCode !== 200) {
      throw new Error(`FNSKU取得に失敗しました (SKU: ${msku}, status: ${responseCode}): ${responseText}`);
    }

    // summariesからfnSkuを取得
    const json = JSON.parse(responseText);
    if (json.summaries && json.summaries.length > 0) {
      const summary = json.summaries[0];
      if (summary.fnSku) {
        return summary.fnSku;
      }
    }

    // fnSkuが見つからない場合はエラーをスロー
    const errorDetails = [];
    if (json.issues && json.issues.length > 0) {
      errorDetails.push(`Issues: ${JSON.stringify(json.issues)}`);
    }
    if (json.summaries && json.summaries.length > 0) {
      errorDetails.push(`Summary found but no fnSku: ${JSON.stringify(json.summaries[0])}`);
    }
    
    throw new Error(`FNSKUが見つかりませんでした (SKU: ${msku})${errorDetails.length > 0 ? ': ' + errorDetails.join(', ') : ''}`);
  }
}
