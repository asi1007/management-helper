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
    this.BASE_URL = "https://sellingpartnerapi-fe.amazon.com/fba/inbound/v0";
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

  _createShipmentPlan(items) {
    const requestItems = items.map(item => ({
      SellerSKU: item.msku,
      ASIN: item.asin,
      Condition: 'NewItem',
      Quantity: item.quantity
    }));

    const payload = {
      ShipToCountryCode: 'JP',
      LabelPrepPreference: 'SELLER_LABEL',
      ShipFromAddress: this.buildSourceAddress(),
      InboundShipmentPlanRequestItems: requestItems
    };

    const options = Object.assign({}, this.options, {
      payload: JSON.stringify(payload)
    });

    const response = UrlFetchApp.fetch(`${this.BASE_URL}/plans`, options);
    const status = response.getResponseCode();
    const body = response.getContentText();
    
    let json;
    try {
      json = JSON.parse(body);
    } catch(parseError) {
      throw new Error(`納品プラン作成APIレスポンスの解析に失敗しました: ${body}`);
    }

    if (status !== 200) {
       const errorMessage = json && json.errors ? JSON.stringify(json.errors) : body;
       throw new Error(`納品プランの作成に失敗しました (status ${status}): ${errorMessage}`);
    }

    return json.payload;
  }

  _createInboundShipment(shipmentId, plan) {
    const shipmentHeader = {
      ShipmentName: `FBA (${Utilities.formatDate(new Date(), 'JST', 'yyyy/MM/dd HH:mm')})`,
      ShipFromAddress: this.buildSourceAddress(),
      DestinationFulfillmentCenterId: plan.DestinationFulfillmentCenterId,
      LabelPrepPreference: 'SELLER_LABEL',
      ShipmentStatus: 'WORKING'
    };

    const shipmentItems = plan.Items.map(item => ({
      SellerSKU: item.SellerSKU,
      QuantityShipped: item.Quantity
    }));

    const payload = {
      InboundShipmentHeader: shipmentHeader,
      InboundShipmentItems: shipmentItems,
      MarketplaceId: DEFAULT_MARKETPLACE_ID
    };

    const options = Object.assign({}, this.options, {
      payload: JSON.stringify(payload)
    });

    const response = UrlFetchApp.fetch(`${this.BASE_URL}/shipments/${shipmentId}`, options);
    const status = response.getResponseCode();
    const body = response.getContentText();

    if (status !== 200) {
      let json;
      try {
        json = JSON.parse(body);
      } catch(e) {
        throw new Error(`納品作成APIレスポンスの解析に失敗しました: ${body}`);
      }
      const errorMessage = json && json.errors ? JSON.stringify(json.errors) : body;
      throw new Error(`納品の作成に失敗しました (shipmentId: ${shipmentId}, status ${status}): ${errorMessage}`);
    }

    return JSON.parse(body).payload;
  }

  createPlan(items){
    // 1. createInboundShipmentPlan
    const planResponse = this._createShipmentPlan(items);
    const createdShipments = [];

    // 2. createInboundShipment for each plan
    for (const plan of planResponse.InboundShipmentPlans) {
      const shipmentId = plan.ShipmentId;
      try {
        this._createInboundShipment(shipmentId, plan);
        createdShipments.push(shipmentId);
        console.log(`納品を作成しました: ${shipmentId}`);
      } catch (e) {
        console.error(`納品の作成に失敗しました (${shipmentId}): ${e.message}`);
        throw e;
      }
    }

    return {
      link: "https://sellercentral.amazon.co.jp/gp/fba/inbound-queue/index.html",
      shipmentIds: createdShipments
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

