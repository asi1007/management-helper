/* exported HomeShipmentSheet */

class HomeShipmentSheet {
  constructor(sheetID, sheetName, setting){
    this.sheet = SpreadsheetApp.openById(sheetID).getSheetByName(sheetName);
    this.setting = setting;
    this.lastRow = this.sheet.getLastRow();
    this.data = this.sheet.getRange(2, 1, this.lastRow, 100).getValues();
  }

  getRowNum(columnName, value) {
    const columnIndex = this.setting.get(columnName);
    for (let i = 0; i < this.data.length; i++) {
      if (String(this.data[i][columnIndex]) === String(value)) {
        return i + 2;
      }
    }
    return null;
  }

  getRowNumsByTracking(trackingNumber) {
    const columnIndex = this.setting.get('追跡番号');
    const rowNums = [];
    for (let i = 0; i < this.data.length; i++) {
      if (String(this.data[i][columnIndex]) === String(trackingNumber)) {
        rowNums.push(i + 2);
      }
    }
    return rowNums;
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
