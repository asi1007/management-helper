/* exported Downloader, InboundPlanCreator, FnskuGetter, MerchantListingsSkuResolver */
// SettingSheetはutilities.jsに移動しました

class Downloader{
  constructor(authToken){
    this.SP_API_URL = "https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20/items/labels";
    this.authToken = authToken;
    this.options = {
      method: 'post',
      muteHttpExceptions : true,
      headers: {
        "Accept" : "application/json",
        "x-amz-access-token": authToken,
        "Content-Type" : "application/json"
      }
    };
  }

  downloadLabels(skuNums, fileName){
    const payload = {
      labelType: 'STANDARD_FORMAT',
      marketplaceId: 'A1VC38T7YXB528',
      mskuQuantities: skuNums,
      localeCode: "ja_JP",
      pageType: 'A4_40_52x29'
    };

    const options = Object.assign({}, this.options, {
      payload: JSON.stringify(payload)
    });

    const response = UrlFetchApp.fetch(this.SP_API_URL, options);
    const responseJson = JSON.parse(response.getContentText());
    console.log('downloadLabels response:', responseJson);

    const fileURI = responseJson.documentDownloads[0].uri;
    const fileResponse = UrlFetchApp.fetch(fileURI, {method:"GET"});
    const pdfBlob = fileResponse.getBlob();

    const folder = DriveApp.getFolderById("1JTpxTG6yyICTlraxY91VLoXzKva0FAIr");
    const file = folder.createFile(pdfBlob.setName(fileName + '.pdf'));
    const fileId = file.getId();
    const downloadUrl = `https://drive.google.com/uc?export=download&id=${fileId}`;

    return {
      url: downloadUrl,
      responseData: responseJson
    };
  }
}

class InboundPlanCreator{
  constructor(authToken){
    this.API_BASE_URL = "https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20";
    // 旧 Inbound Shipment API (v0) は QuantityShipped/QuantityReceived を返すことが多いためフォールバック先として保持
    this.LEGACY_INBOUND_V0_BASE_URL = "https://sellingpartnerapi-fe.amazon.com/fba/inbound/v0";
    this.PLAN_LINK_BASE = "https://sellercentral.amazon.co.jp";
    this.authToken = authToken;
    this.options = {
      method: 'post',
      muteHttpExceptions: true,
      headers: {
        "Accept": "application/json",
        "x-amz-access-token": authToken,
        "Content-Type": "application/json"
      }
    };
  }

  _requestJson_(url, method = 'get', payloadObj = null) {
    const options = {
      method: method,
      muteHttpExceptions: true,
      headers: {
        "Accept": "application/json",
        "x-amz-access-token": this.authToken,
        "Content-Type": "application/json"
      }
    };
    if (payloadObj) {
      options.payload = JSON.stringify(payloadObj);
    }
    const res = UrlFetchApp.fetch(url, options);
    const status = res.getResponseCode();
    const body = res.getContentText();
    if (status < 200 || status >= 300) {
      throw new Error(`SP-API request failed (status ${status}): ${body}`);
    }
    return body ? JSON.parse(body) : {};
  }

  /**
   * Inbound Plan の shipments を取得する（作成/確定と独立して参照したい用途向け）
   * @param {string} inboundPlanId
   * @returns {any[]} shipments
   */
  listShipments(inboundPlanId) {
    return this._listShipments(inboundPlanId);
  }

  /**
   * Shipment の items を取得する（QuantityShipped / QuantityReceived を含むことを期待）
   * まず 2024-03-20 のパスを試し、失敗したら v0 にフォールバックする。
   * @param {string} shipmentId
   * @returns {any[]} items
   */
  getShipmentItems(shipmentId) {
    const sid = String(shipmentId || '').trim();
    if (!sid) throw new Error('shipmentId が空です');

    const candidates = [
      // 2024-03-20 (推定) パス
      `${this.API_BASE_URL}/shipments/${encodeURIComponent(sid)}/items`,
      // v0 フォールバック (MarketplaceId パラメータが必要なことが多い)
      `${this.LEGACY_INBOUND_V0_BASE_URL}/shipments/${encodeURIComponent(sid)}/items?MarketplaceId=${DEFAULT_MARKETPLACE_ID}`,
    ];

    const errors = [];
    for (const url of candidates) {
      try {
        const json = this._requestJson_(url, 'get');
        const items = this._extractItemsArray_(json);
        if (items.length === 0) {
          console.warn(`[InboundItems] empty items: shipmentId=${sid} url=${url}`);
        }
        return items;
      } catch (e) {
        errors.push({ url, message: String(e && e.message || e) });
      }
    }

    throw new Error(`[InboundItems] items取得に失敗: shipmentId=${sid}, errors=${JSON.stringify(errors)}`);
  }

  _extractItemsArray_(json) {
    const j = json || {};
    // ありがちな形を順番に拾う
    if (Array.isArray(j.items)) return j.items;
    if (Array.isArray(j.payload)) return j.payload;
    if (j.payload && Array.isArray(j.payload.items)) return j.payload.items;
    if (j.payload && Array.isArray(j.payload.member)) return j.payload.member;
    if (j.payload && Array.isArray(j.payload.ItemData)) return j.payload.ItemData;
    if (j.payload && Array.isArray(j.payload.itemData)) return j.payload.itemData;
    return [];
  }

  /**
   * inboundPlanId から shipment items を集計して、QuantityShipped/Received の合計を返す
   * @param {string} inboundPlanId
   * @returns {{quantityShipped:number, quantityReceived:number, shipmentIds:string[]}}
   */
  getPlanQuantityTotals(inboundPlanId) {
    const planId = String(inboundPlanId || '').trim();
    if (!planId) throw new Error('inboundPlanId が空です');

    const shipments = this._listShipments(planId);
    const shipmentIds = (shipments || []).map(s => s && s.shipmentId ? String(s.shipmentId) : '').filter(Boolean);
    if (shipmentIds.length === 0) {
      console.warn(`[InboundItems] shipmentsなし: inboundPlanId=${planId}`);
      return { quantityShipped: 0, quantityReceived: 0, shipmentIds: [] };
    }

    let shipped = 0;
    let received = 0;
    for (const sid of shipmentIds) {
      const items = this.getShipmentItems(sid);
      for (const it of (items || [])) {
        const qS = Number(
          (it && (it.quantityShipped ?? it.QuantityShipped ?? it.quantity_shipped)) || 0
        );
        const qR = Number(
          (it && (it.quantityReceived ?? it.QuantityReceived ?? it.quantity_received)) || 0
        );
        if (qS) shipped += qS;
        if (qR) received += qR;
      }
    }

    console.log(`[InboundItems] totals: inboundPlanId=${planId} shipped=${shipped} received=${received} shipments=${JSON.stringify(shipmentIds)}`);
    return { quantityShipped: shipped, quantityReceived: received, shipmentIds };
  }

  /**
   * placementOptions のログ表示用に、できるだけ壊れない概要を作る
   * @param {any} option
   * @returns {Object}
   */
  _summarizePlacementOption(option) {
    const o = option || {};
    const summary = {
      placementOptionId: o.placementOptionId || o.placementOptionID || o.id || null,
    };

    // よくありそうなフィールドを、あれば載せる（無ければ無視）
    const maybeKeys = [
      'fees',
      'fee',
      'totalFees',
      'charges',
      'transportationMode',
      'shippingMode',
      'shippingMethod',
      'mode',
      'shipmentIds',
      'shipments',
      'destinationFulfillmentCenters',
      'assignedShipments',
      'placementFee',
      'isRecommended',
      'recommended',
      'splitShipments',
      'distribution',
      'inboundPlanId',
    ];
    for (const k of maybeKeys) {
      if (o[k] !== undefined) summary[k] = o[k];
    }

    // フィールド名が揺れても拾えるように、mode/transport/shipping/pallet を含むプリミティブ値を追加
    try {
      const extraKeys = Object.keys(o).filter(k => /mode|transport|shipping|pallet/i.test(k));
      let added = 0;
      for (const k of extraKeys) {
        if (summary[k] !== undefined) continue;
        const v = o[k];
        const t = typeof v;
        if (v === null || v === undefined) continue;
        if (t === 'string' || t === 'number' || t === 'boolean') {
          summary[k] = v;
          added++;
        }
        if (added >= 15) break;
      }
    } catch (e) {
      // ignore
    }

    // パレット/LTL系の判定（ワークフロー分岐に関係するため、常にログに含める）
    summary.isPalletLike = this._isPalletLikePlacementOption(o);
    return summary;
  }

  /**
   * placement option がパレット/LTL系ワークフローっぽいかを雑に判定する
   * @param {any} option
   * @returns {boolean}
   */
  _isPalletLikePlacementOption(option) {
    const o = option || {};
    const values = [];
    try {
      for (const k of Object.keys(o)) {
        const v = o[k];
        if (v === null || v === undefined) continue;
        if (typeof v === 'string') values.push(v);
        if (typeof v === 'number') values.push(String(v));
      }
    } catch (e) {}
    const joined = values.join(' ').toLowerCase();
    // 代表例: pallet / ltl / freight など
    return /pallet|ltl|freight|truckload|truck/i.test(joined);
  }

  /**
   * placementOptions の候補概要をログに出す（毎回）
   * @param {string} inboundPlanId
   * @param {any[]} options
   */
  _logPlacementOptionsOverview(inboundPlanId, options) {
    const list = Array.isArray(options) ? options : [];
    let palletCount = 0;
    for (const o of list) {
      if (this._isPalletLikePlacementOption(o)) palletCount++;
    }
    console.log(`[PlacementOptions] inboundPlanId=${inboundPlanId}, count=${list.length}, palletLike=${palletCount}, nonPallet=${list.length - palletCount}`);
    for (let i = 0; i < list.length; i++) {
      const summary = this._summarizePlacementOption(list[i]);
      console.log(`[PlacementOptions] #${i + 1}/${list.length}: ${JSON.stringify(summary)}`);
    }
  }

  /**
   * Placement Options を生成→完了待ち→一覧取得し、毎回ログに概要を出す
   * @param {string} inboundPlanId
   * @returns {any[]} placementOptions
   */
  getPlacementOptions(inboundPlanId) {
    const generateOpId = this._generatePlacementOptions(inboundPlanId);
    this._pollOperation(generateOpId, "Placement Options Generation");
    const options = this._listPlacementOptions(inboundPlanId);
    this._logPlacementOptionsOverview(inboundPlanId, options);
    return options;
  }

  /**
   * Placement Option を確定し、選択結果（概要＋shipmentIds）を毎回ログに出す
   * @param {string} inboundPlanId
   * @param {string} placementOptionId
   * @returns {any[]} shipments
   */
  confirmPlacementOption(inboundPlanId, placementOptionId) {
    console.log(`[PlacementOptions] Selected placementOptionId=${placementOptionId} (inboundPlanId=${inboundPlanId})`);
    const confirmOpId = this._confirmPlacementOption(inboundPlanId, placementOptionId);
    this._pollOperation(confirmOpId, "Placement Option Confirmation");
    const shipments = this._listShipments(inboundPlanId);
    const shipmentIds = (shipments || []).map(s => s.shipmentId).filter(Boolean);
    console.log(`[PlacementOptions] Confirmed placementOptionId=${placementOptionId} -> shipments=${JSON.stringify(shipmentIds)}`);
    return shipments;
  }

  /**
   * Inbound Plan 作成の operationId を待機する（= 1.5）
   * @param {string} operationId
   */
  waitInboundPlanCreation(operationId) {
    if (!operationId) {
      throw new Error('operationId が空のため Inbound Plan Creation を待機できません');
    }
    this._pollOperation(operationId, "Inbound Plan Creation");
  }

  buildSourceAddress(){
    const filtered = {};
    Object.keys(SHIP_FROM_ADDRESS).forEach(key => {
      const value = SHIP_FROM_ADDRESS[key];
      if (value !== undefined && value !== null && value !== '') {
        filtered[key] = value;
      }
    });
    return filtered;
  }

  _parseErrorsFromMessage(errorMessage) {
    const jsonMatch = errorMessage.match(/\[.*\]/);
    if (!jsonMatch) return null;
    try {
      return JSON.parse(jsonMatch[0]);
    } catch (jsonError) {
      return null;
    }
  }

  _handlePrepOwnerError(error, itemMap, regex, newOwnerValue, logMessage) {
    const match = error.message.match(regex);
    if (match) {
      const msku = match[1];
      const item = itemMap.get(msku);
      if (item) {
        console.log(logMessage.replace('${msku}', msku));
        item.prepOwner = newOwnerValue;
        return true;
      }
    }
    return false;
  }

  _createInboundPlanWithRetry(items) {
    let currentItems = items.map(item => ({
      msku: item.msku,
      quantity: item.quantity,
      labelOwner: item.labelOwner || 'SELLER',
      prepOwner: item.prepOwner || 'NONE' // 初期値NONE
    }));

    let retryCount = 0;
    const MAX_RETRIES = 3;

    while (true) {
      try {
        return this._createInboundPlan(currentItems);
      } catch (e) {
        if (retryCount >= MAX_RETRIES) {
          console.error(`最大リトライ回数(${MAX_RETRIES})を超えました。最後のエラー: ${e.message}`);
          throw e;
        }

        const errors = this._parseErrorsFromMessage(e.message);
        if (!errors) throw e;

        const itemMap = new Map(currentItems.map(item => [item.msku, item]));
        let needsRetry = false;

        for (const error of errors) {
          const requiresPrep = this._handlePrepOwnerError(
            error, itemMap, /ERROR: (.+?) requires prepOwner/, 'SELLER',
            'SKU ${msku} は梱包が必要なため、prepOwnerをSELLERに変更します。'
          );
          const notRequiresPrep = this._handlePrepOwnerError(
            error, itemMap, /ERROR: (.+?) does not require prepOwner/, 'NONE',
            'SKU ${msku} は梱包不要なため、prepOwnerをNONEに変更します。'
          );
          needsRetry = needsRetry || requiresPrep || notRequiresPrep;
        }

        if (!needsRetry) throw e;
        
        console.log(`prepOwner設定を修正して再試行します (${retryCount + 1}/${MAX_RETRIES})`);
        retryCount++;
      }
    }
  }

  _createInboundPlan(items) {
    const payload = {
      destinationMarketplaces: [DEFAULT_MARKETPLACE_ID],
      sourceAddress: this.buildSourceAddress(),
      items: items,
      name: `Inbound ${Utilities.formatDate(new Date(), 'JST', 'yyyy-MM-dd HH:mm')}`
    };

    const options = Object.assign({}, this.options, {
      payload: JSON.stringify(payload)
    });

    const response = UrlFetchApp.fetch(`${this.API_BASE_URL}/inboundPlans`, options);
    const status = response.getResponseCode();
    const body = response.getContentText();
    
    if (status !== 202) {
      let json;
      try { json = JSON.parse(body); } catch(e) {}
      const errorMessage = json && json.errors ? JSON.stringify(json.errors) : body;
      throw new Error(`納品プランの作成に失敗しました (status ${status}): ${errorMessage}`);
    }

    return JSON.parse(body);
  }

  _generatePlacementOptions(inboundPlanId) {
    const response = UrlFetchApp.fetch(`${this.API_BASE_URL}/inboundPlans/${inboundPlanId}/placementOptions`, this.options);
    const status = response.getResponseCode();
    const body = response.getContentText();
    
    if (status !== 202) {
      throw new Error(`Placement Options 生成に失敗しました (status ${status}): ${body}`);
    }
    return JSON.parse(body).operationId;
  }

  _pollOperation(operationId, operationName) {
    console.log(`${operationName} 待機中... (OperationId: ${operationId})`);
    const start = Date.now();
    const timeout = 300000; // 5分

    while (Date.now() - start < timeout) {
      Utilities.sleep(5000);
      try {
        console.log(`${operationName}: ステータス確認リクエスト送信...`);
        const response = UrlFetchApp.fetch(`${this.API_BASE_URL}/operations/${operationId}`, {
          headers: this.options.headers,
          muteHttpExceptions: true
        });
        console.log(`${operationName}: レスポンス受信 (Status Code: ${response.getResponseCode()})`);
        
        const json = JSON.parse(response.getContentText());
        console.log(`${operationName} status: ${json.operationStatus}`);
        
        if (json.operationStatus === 'SUCCESS') {
          console.log(`${operationName} 完了`);
          return;
        } else if (json.operationStatus === 'FAILED') {
          throw new Error(`${operationName} 失敗: ${JSON.stringify(json.operationProblems)}`);
        }
      } catch (e) {
        console.warn(`${operationName} ポーリング中にエラー (再試行します): ${e.message}`);
      }
    }
    throw new Error(`${operationName} タイムアウト`);
  }

  _listPlacementOptions(inboundPlanId) {
    const response = UrlFetchApp.fetch(`${this.API_BASE_URL}/inboundPlans/${inboundPlanId}/placementOptions`, {
      headers: this.options.headers,
      muteHttpExceptions: true
    });
    const json = JSON.parse(response.getContentText());
    if (!json.placementOptions || json.placementOptions.length === 0) {
      throw new Error('有効なPlacement Optionsがありません');
    }
    return json.placementOptions;
  }

  _confirmPlacementOption(inboundPlanId, placementOptionId) {
    const response = UrlFetchApp.fetch(`${this.API_BASE_URL}/inboundPlans/${inboundPlanId}/placementOptions/${placementOptionId}/confirmation`, this.options);
    const status = response.getResponseCode();
    const body = response.getContentText();
    
    if (status !== 202) {
       throw new Error(`Placement Option 確定に失敗しました (status ${status}): ${body}`);
    }
    return JSON.parse(body).operationId;
  }
  
  _listShipments(inboundPlanId) {
    const response = UrlFetchApp.fetch(`${this.API_BASE_URL}/inboundPlans/${inboundPlanId}/shipments`, {
      headers: this.options.headers,
      muteHttpExceptions: true
    });
    return JSON.parse(response.getContentText()).shipments || [];
  }

  createPlan(items){
    // 1. 納品プラン作成 (リトライ付き)
    const planResult = this._createInboundPlanWithRetry(items);
    const inboundPlanId = planResult.inboundPlanId;
    const createOperationId = planResult.operationId;
    console.log(`Inbound Plan Created: ${inboundPlanId} (Operation: ${createOperationId})`);

    // 1.5〜5 は「コメントアウト部分を復活」したもの。
    // ただし、UI(フォーム)で選ぶ場合はこの関数内で入力待ちできないため、
    // ここでは「候補生成＆一覧ログ」までをデフォルトで実行する。
    //
    // 必要なら呼び出し側で `confirmPlacementOption(inboundPlanId, placementOptionId)` を呼んで確定する。
    // （UI選択フローは usecases/inboundPlan.js の createInboundPlanFromActiveRowsWithPlacementSelection を利用）

    // 1.5 プラン作成完了待機
    this.waitInboundPlanCreation(createOperationId);

    // 2-3 Placement Options 生成→一覧取得（毎回候補概要ログ）
    const placementOptions = this.getPlacementOptions(inboundPlanId);

    return {
      inboundPlanId,
      operationId: planResult.operationId,
      link: `${this.PLAN_LINK_BASE}/fba/sendtoamazon/pack_later_confirm_shipments?wf=${inboundPlanId}`,
      shipmentIds: [],
      placementOptions
    };
  }
}

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
