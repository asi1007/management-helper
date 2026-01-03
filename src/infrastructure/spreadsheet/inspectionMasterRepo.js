/* exported InspectionMasterRepo */

class InspectionMasterRepo extends IInspectionMasterRepository {
  /**
   * @param {string} spreadsheetId
   * @param {number|null} sheetGid
   */
  constructor(spreadsheetId, sheetGid = null) {
    super();
    this.spreadsheetId = spreadsheetId;
    this.sheetGid = sheetGid;
  }

  /**
   * @returns {InspectionMasterCatalog}
   */
  load() {
    const result = new Map();

    const ss = SpreadsheetApp.openById(this.spreadsheetId);
    const sheet = this.sheetGid ? ss.getSheetById(Number(this.sheetGid)) : ss.getActiveSheet();
    if (!sheet) {
      throw new Error(`詳細検品マスタのシートが見つかりません (spreadsheetId=${this.spreadsheetId}, gid=${this.sheetGid})`);
    }

    const lastRow = sheet.getLastRow();
    const lastCol = sheet.getLastColumn();
    if (lastRow < 2 || lastCol < 1) {
      return new InspectionMasterCatalog(result);
    }

    const values = sheet.getRange(1, 1, lastRow, lastCol).getValues();
    const headers = (values[0] || []).map(h => String(h || '').trim());

    // 仕様固定:
    // - ASINはA列
    // - 商品名はヘッダー「商品名」
    // - 検品箇所はヘッダー「検品箇所」
    // - 詳細指示書URLはヘッダー「詳細指示書URL」
    const asinCol = 0;
    const productNameCol = headers.indexOf('商品名');
    if (productNameCol === -1) {
      throw new Error(`詳細検品マスタのヘッダー「商品名」が見つかりません。現在のヘッダー: ${JSON.stringify(headers)}`);
    }
    const inspectionCol = headers.indexOf('検品箇所');
    if (inspectionCol === -1) {
      throw new Error(`詳細検品マスタのヘッダー「検品箇所」が見つかりません。現在のヘッダー: ${JSON.stringify(headers)}`);
    }
    const detailInstructionUrlCol = headers.indexOf('詳細指示書URL');
    if (detailInstructionUrlCol === -1) {
      throw new Error(`詳細検品マスタのヘッダー「詳細指示書URL」が見つかりません。現在のヘッダー: ${JSON.stringify(headers)}`);
    }

    for (let r = 1; r < values.length; r++) {
      const row = values[r];
      const asin = String(row[asinCol] || '').trim();
      if (!asin) continue;
      const productName = String(row[productNameCol] || '').trim();
      const inspectionPoint = String(row[inspectionCol] || '').trim();
      if (!inspectionPoint) continue; // 検品内容が空なら対象外
      const detailInstructionUrl = String(row[detailInstructionUrlCol] || '').trim();
      result.set(asin, new InspectionMasterItem(asin, productName, inspectionPoint, detailInstructionUrl));
    }

    return new InspectionMasterCatalog(result);
  }
}


