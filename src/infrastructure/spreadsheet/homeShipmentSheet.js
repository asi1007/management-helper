/* exported HomeShipmentSheet */

class HomeShipmentSheet extends BaseSheet {
  constructor(sheetID, sheetName){
    super(sheetID, sheetName);
    this.headers = this.data[1]; 
  }

  getColumnIndex(columnName) {
    const index = this.headers.indexOf(columnName);
    if (index === -1) {
      throw new Error(`列 "${columnName}" が見つかりません`);
    }
    return index;
  }

  getValue(rowID, columnName) {
    const columnIndex = this.getColumnIndex(columnName);
    return this.sheet.getRange(rowID, columnIndex + 1).getValue();
  }

  getRowIdsByTracking() {
    const tracking= getActiveValue('追跡番号');
    
    for (let i = 0; i < this.data.length; i++) {
      rowIds = tracking ("行番号");
      if (String(this.data[i][trackingColumnIndex]) === String(trackingNumber)) {
        rowIds.push(this.data[i][rowIdColumnIndex]);
      }
    }
    return rowIds;
  }
}
