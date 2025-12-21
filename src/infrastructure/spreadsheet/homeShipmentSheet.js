/* exported HomeShipmentSheet */

class HomeShipmentSheet {
  constructor(sheetID, sheetName, setting){
    this.sheet = SpreadsheetApp.openById(sheetID).getSheetByName(sheetName);
    this.lastRow = this.sheet.getLastRow();
    this.data = this.sheet.getRange(2, 1, this.lastRow, 100).getValues();
    // 3行目をヘッダーとして取得（配列インデックスは1）
    this.headers = this.data[1]; 
  }

  getColumnIndex(columnName) {
    const index = this.headers.indexOf(columnName);
    if (index === -1) {
      throw new Error(`列 "${columnName}" が見つかりません`);
    }
    return index;
  }

  getRowNum(columnName, value) {
    const columnIndex = this.getColumnIndex(columnName);
    for (let i = 0; i < this.data.length; i++) {
      if (String(this.data[i][columnIndex]) === String(value)) {
        return i + 2;
      }
    }
    return null;
  }

  getRowIdsByTracking(trackingNumber) {
    const trackingColumnIndex = this.getColumnIndex('追跡番号');
    const rowIdColumnIndex = this.getColumnIndex('行番号');
    const rowIds = [];
    
    for (let i = 0; i < this.data.length; i++) {
      if (String(this.data[i][trackingColumnIndex]) === String(trackingNumber)) {
        rowIds.push(this.data[i][rowIdColumnIndex]);
      }
    }
    return rowIds;
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
