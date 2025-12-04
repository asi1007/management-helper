/* exported Downloader, InboundPlanCreator, FnskuGetter, Sheet */
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
        console.log(`${operationName} status: ${json.status}`);
        
        if (json.status === 'SUCCEEDED') {
          console.log(`${operationName} 完了`);
          return;
        } else if (json.status === 'FAILED') {
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

    // 1.5 プラン作成完了待機
    this._pollOperation(createOperationId, "Inbound Plan Creation");

    // 2. Placement Options 生成
    const generateOpId = this._generatePlacementOptions(inboundPlanId);
    this._pollOperation(generateOpId, "Placement Options Generation");

    // 3. オプション取得と選択
    const options = this._listPlacementOptions(inboundPlanId);
    // 最初のオプションを選択（手数料なしや分割なしなどのロジックがあればここに追加）
    const selectedOption = options[0];
    console.log(`Selected Placement Option: ${selectedOption.placementOptionId}`);

    // 4. オプション確定
    const confirmOpId = this._confirmPlacementOption(inboundPlanId, selectedOption.placementOptionId);
    this._pollOperation(confirmOpId, "Placement Option Confirmation");

    // 5. Shipment情報取得
    const shipments = this._listShipments(inboundPlanId);
    console.log(`Shipments Created: ${shipments.map(s => s.shipmentId).join(', ')}`);

    return {
      inboundPlanId,
      operationId: planResult.operationId,
      link: `${this.PLAN_LINK_BASE}/fba/sendtoamazon/pack_later_confirm_shipments?wf=${inboundPlanId}`,
      shipmentIds: shipments.map(s => s.shipmentId)
    };
  }
}

class FnskuGetter{
  constructor(authToken){
    this.authToken = authToken;
    this.LISTINGS_API_URL = "https://sellingpartnerapi-fe.amazon.com/listings/2021-08-01/items/APS8L6SC4MEPF/";
  }

  getFnsku(msku) {
    const options = {
      method: 'get',
      muteHttpExceptions: true,
      headers: {
        "Accept": "application/json",
        "x-amz-access-token": this.authToken
      }
    };

    const url = `${this.LISTINGS_API_URL}${msku}?marketplaceIds=A1VC38T7YXB528`;
    const response = UrlFetchApp.fetch(url, options);

    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
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

// SettingSheetクラスはutilities.jsに移動しました

class Sheet{
  constructor(sheetID, sheetName, setting){
    this.sheet = SpreadsheetApp.openById(sheetID).getSheetByName(sheetName);
    this.setting = setting;
    this.lastRow = this.sheet.getLastRow();
    this.data = this.sheet.getRange(2, 1, this.lastRow, 100).getValues();
    this.rowNumbers = [];
  }

  getActiveRowData(){
    const activeSpreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    const activeSheet = activeSpreadsheet.getActiveSheet();

    // 2. 選択された行番号を取得
    const selectedRowNumbers = this._getSelectedRowNumbers(activeSheet);
    const sortedRowNumbers = Array.from(selectedRowNumbers).sort((a, b) => a - b);

    const selectedRows = [];
    const finalRowNumbers = [];

    // 3. 行番号に対応するデータを抽出
    for (const rowNum of sortedRowNumbers) {
      // フィルタまたは手動で非表示になっている行はスキップ
      const isHiddenByFilter = activeSheet.isRowHiddenByFilter(rowNum);
      const isHiddenByUser = activeSheet.isRowHiddenByUser(rowNum);
      const isHidden = isHiddenByFilter || isHiddenByUser;
      
      console.log(`行番号 ${rowNum}: フィルタ非表示=${isHiddenByFilter}, 手動非表示=${isHiddenByUser}, 判定=${isHidden ? 'スキップ' : '対象'}`);
      
      if (isHidden) {
        continue;
      }

      // データ配列は0始まり、行番号は1始まり、ヘッダーが1行あるため -2
      const dataIndex = rowNum - 2;

      // データ範囲外の行はスキップ
      if (dataIndex < 0 || dataIndex >= this.data.length) {
        continue;
      }

      const rowData = this.data[dataIndex];
      selectedRows.push(rowData);
      finalRowNumbers.push(rowNum);
    }

    // インスタンスの状態を更新
    this.data = selectedRows;
    this.rowNumbers = finalRowNumbers;

    console.log(`選択された行: [${finalRowNumbers.join(', ')}]`);

    return selectedRows;
  }

  _getSelectedRowNumbers(activeSheet) {
    const selectedRowNumbers = new Set();
    const activeRangeList = activeSheet.getActiveRangeList();

    // 複数範囲選択に対応
    if (activeRangeList && activeRangeList.getRanges().length > 0) {
      const ranges = activeRangeList.getRanges();
      for (const range of ranges) {
        this._addSelectedRowNumbers(selectedRowNumbers, range);
      }
    } else {
      const activeRange = activeSheet.getActiveRange();
      this._addSelectedRowNumbers(selectedRowNumbers, activeRange);
    }
    return selectedRowNumbers;
  }

  _addSelectedRowNumbers(selectedRowNumbers, activeRange){
      const startRow = activeRange.getRow();
      const numRows = activeRange.getNumRows();
      for (let i = 0; i < numRows; i++) {
        selectedRowNumbers.add(startRow + i);
      }
      return selectedRowNumbers;
  }

  writeColumn(columnName, value){
    try {
      const column = this.setting.get(columnName) + 1;
      let successCount = 0;
      
      for (const rowNum of this.rowNumbers) {
          if (typeof value === 'object' && value.type === 'formula') {
            this.sheet.getRange(rowNum, column).setFormula(value.value);
          } else {
            this.sheet.getRange(rowNum, column).setValue(value);
          }
          successCount++;
      }
      console.log(`${columnName}を${successCount}行に書き込みました`);
    } catch (e) {
      console.warn(`${columnName}への書き込みに失敗しました: ${e.message}`);
      throw e;
    }
  }

  writeCell(rowNum, columnNum, value){
    try {
      if (typeof value === 'object' && value.type === 'formula') {
        this.sheet.getRange(rowNum, columnNum).setFormula(value.value);
      } else {
        this.sheet.getRange(rowNum, columnNum).setValue(value);
      }
      console.log(`${rowNum}行目の${columnNum}に書き込みました`);
    } catch (e) {
      console.warn(`${rowNum}行目の${columnNum}への書き込みに失敗しました: ${e.message}`);
      throw e;
    }
  }

}

