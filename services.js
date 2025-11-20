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
    this.API_URL = "https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20/inboundPlans";
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

  createPlan(items){
    const requestItems = items.map(item => {
      const planItem = {
        msku: item.msku,
        quantity: item.quantity,
        labelOwner: item.labelOwner || 'SELLER',
        prepOwner: item.prepOwner || 'SELLER'
      };
      if (item.expiration) {
        planItem.expiration = item.expiration;
      }
      if (item.manufacturingLotCode) {
        planItem.manufacturingLotCode = item.manufacturingLotCode;
      }
      return planItem;
    });

    const payload = {
      destinationMarketplaces: [DEFAULT_MARKETPLACE_ID],
      sourceAddress: this.buildSourceAddress(),
      items: requestItems,
      name: `Inbound ${Utilities.formatDate(new Date(), 'JST', 'yyyy-MM-dd HH:mm')}`
    };

    const options = Object.assign({}, this.options, {
      payload: JSON.stringify(payload)
    });

    const response = UrlFetchApp.fetch(this.API_URL, options);
    const status = response.getResponseCode();
    const body = response.getContentText();
    let json;
    try{
      json = JSON.parse(body);
    }catch(parseError){
      throw new Error(`納品プランAPIレスポンスの解析に失敗しました: ${body}`);
    }

    if (status !== 202) {
      const errorMessage = json && json.errors ? JSON.stringify(json.errors) : body;
      throw new Error(`納品プランの作成に失敗しました (status ${status}): ${errorMessage}`);
    }

    const inboundPlanId = json.inboundPlanId;
    const operationId = json.operationId;
    if (!inboundPlanId) {
      throw new Error(`納品プランレスポンスに inboundPlanId が含まれていません: ${body}`);
    }

    const link = `${this.PLAN_LINK_BASE}/fba/sendtoamazon/pack_later_confirm_shipments?wf=${inboundPlanId}`;

    return {
      inboundPlanId,
      operationId,
      link
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

    if (activeSheet.getName() !== this.sheet.getName()) {
      throw new Error('アクティブセルが対象シートではありません');
    }

    const selectedRowNumbers = new Set();
    const activeRangeList = activeSheet.getActiveRangeList();
    if (activeRangeList && activeRangeList.getRanges().length > 0) {
      const ranges = activeRangeList.getRanges();
      for (let rangeIndex = 0; rangeIndex < ranges.length; rangeIndex++) {
        const range = ranges[rangeIndex];
        const startRow = range.getRow();
        const numRows = range.getNumRows();
        for (let i = 0; i < numRows; i++) {
          selectedRowNumbers.add(startRow + i);
        }
      }
    } else {
      const activeRange = activeSheet.getActiveRange();
      if (!activeRange) {
        throw new Error('アクティブセルが選択されていません');
      }

      const startRow = activeRange.getRow();
      const numRows = activeRange.getNumRows();
      for (let i = 0; i < numRows; i++) {
        selectedRowNumbers.add(startRow + i);
      }
    }

    const sortedRowNumbers = Array.from(selectedRowNumbers).sort((a, b) => a - b);

    const selectedRows = [];
    const finalRowNumbers = [];

    for (const rowNum of sortedRowNumbers) {
      const dataIndex = rowNum - 2;

      if (dataIndex < 0 || dataIndex >= this.data.length) {
        continue;
      }

      const rowData = this.data[dataIndex];
      selectedRows.push(rowData);
      finalRowNumbers.push(rowNum);
    }

    if (selectedRows.length === 0) {
      throw new Error('有効な行が選択されていません');
    }

    this.data = selectedRows;
    this.rowNumbers = finalRowNumbers;

    return selectedRows;
  }

  writeColumn(columnName, value){
    try {
      const column = this.setting.get(columnName) + 1;
      let successCount = 0;
      
      for (let i = 0; i < this.rowNumbers.length; i++) {
        const rowNum = this.rowNumbers[i];
        if (rowNum) {
          if (typeof value === 'object' && value.type === 'formula') {
            this.sheet.getRange(rowNum, column).setFormula(value.value);
          } else {
            this.sheet.getRange(rowNum, column).setValue(value);
          }
          successCount++;
        }
      }
      console.log(`${columnName}を${successCount}行に書き込みました`);
    } catch (e) {
      console.warn(`${columnName}への書き込みに失敗しました: ${e.message}`);
      throw e;
    }
  }

  writeCell(rowNum, columnName, value){
    try {
      const column = this.setting.get(columnName) + 1;
      if (typeof value === 'object' && value.type === 'formula') {
        this.sheet.getRange(rowNum, column).setFormula(value.value);
      } else {
        this.sheet.getRange(rowNum, column).setValue(value);
      }
      console.log(`${rowNum}行目の${columnName}に書き込みました`);
    } catch (e) {
      console.warn(`${rowNum}行目の${columnName}への書き込みに失敗しました: ${e.message}`);
      throw e;
    }
  }

}


