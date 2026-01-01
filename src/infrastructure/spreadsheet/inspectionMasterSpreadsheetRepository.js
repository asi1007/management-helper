/* exported InspectionMasterSpreadsheetRepository */

class InspectionMasterSpreadsheetRepository extends IInspectionMasterRepository {
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
   * @param {string[]} asins
   * @returns {Map<string, InspectionMasterItem>}
   */
  findByAsins(asins) {
    const asinSet = new Set((asins || []).map(a => String(a || '').trim()).filter(Boolean));
    const result = new Map();
    if (asinSet.size === 0) {
      return result;
    }

    const ss = SpreadsheetApp.openById(this.spreadsheetId);
    const sheet = this.sheetGid ? ss.getSheetById(Number(this.sheetGid)) : ss.getActiveSheet();
    if (!sheet) {
      throw new Error(`詳細検品マスタのシートが見つかりません (spreadsheetId=${this.spreadsheetId}, gid=${this.sheetGid})`);
    }

    const lastRow = sheet.getLastRow();
    const lastCol = sheet.getLastColumn();
    if (lastRow < 2 || lastCol < 1) {
      return result;
    }

    const values = sheet.getRange(1, 1, lastRow, lastCol).getValues();
    const headers = (values[0] || []).map(h => String(h || '').trim());

    // 仕様固定:
    // - ASINはA列
    // - 検品内容はヘッダー「検品内容」
    const asinCol = 0;
    const inspectionCol = headers.indexOf('検品内容');
    if (inspectionCol === -1) {
      throw new Error(`詳細検品マスタのヘッダー「検品内容」が見つかりません。現在のヘッダー: ${JSON.stringify(headers)}`);
    }

    for (let r = 1; r < values.length; r++) {
      const row = values[r];
      const asin = String(row[asinCol] || '').trim();
      if (!asin || !asinSet.has(asin)) continue;
      const inspectionPoint = String(row[inspectionCol] || '').trim();
      // 検品内容が空なら「検品対象なし」とみなす
      if (!inspectionPoint) continue;
      result.set(asin, new InspectionMasterItem(asin, inspectionPoint));
    }

    return result;
  }

  /**
   * @param {string[]} headers
   * @param {string[]} candidates
   * @returns {number}
   */
  _findHeaderIndex(headers, candidates) {
    for (const c of candidates) {
      const idx = headers.indexOf(c);
      if (idx !== -1) return idx;
    }
    return -1;
  }
}


