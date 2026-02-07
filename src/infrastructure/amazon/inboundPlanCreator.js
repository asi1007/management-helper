/* exported InboundPlanCreator */

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
   * shipmentId からステータスを取得する（v0 API）
   * @param {string} shipmentId
   * @returns {string} shipmentStatus (WORKING, SHIPPED, IN_TRANSIT, RECEIVING, CLOSED, etc.)
   */
  getShipmentStatus(shipmentId) {
    const sid = String(shipmentId || '').trim();
    if (!sid) throw new Error('shipmentId が空です');

    const url = `${this.LEGACY_INBOUND_V0_BASE_URL}/shipments?ShipmentIdList=${encodeURIComponent(sid)}&QueryType=SHIPMENT&MarketplaceId=${DEFAULT_MARKETPLACE_ID}`;
    const json = this._requestJson_(url, 'get');
    console.log(`[ShipmentStatus] shipmentId=${sid} raw=${JSON.stringify(json)}`);

    const shipments = (json.payload && json.payload.ShipmentData) || [];
    for (const s of shipments) {
      if (String(s.ShipmentId || '') === sid) {
        return String(s.ShipmentStatus || '');
      }
    }
    return '';
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
        console.log(`[InboundItems] response: shipmentId=${sid} raw=${JSON.stringify(json)}`);
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
   * shipmentId から直接 items を取得して、QuantityShipped/Received の合計を返す
   * @param {string} shipmentId
   * @returns {{quantityShipped:number, quantityReceived:number}}
   */
  getShipmentQuantityTotals(shipmentId) {
    const sid = String(shipmentId || '').trim();
    if (!sid) throw new Error('shipmentId が空です');

    const items = this.getShipmentItems(sid);
    let shipped = 0;
    let received = 0;
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

    console.log(`[InboundItems] shipment totals: shipmentId=${sid} shipped=${shipped} received=${received}`);
    return { quantityShipped: shipped, quantityReceived: received };
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
