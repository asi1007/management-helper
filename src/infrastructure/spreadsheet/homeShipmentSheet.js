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

  getActiveValues(columnName) {
    const selectedRowNumbers = this._getSelectedRowNumbers(this.sheet);
    const sortedRowNumbers = Array.from(selectedRowNumbers).sort((a, b) => a - b);
    const columnIndex = this.getColumnIndex(columnName);
    const values = [];

    for (const rowNum of sortedRowNumbers) {
      const isHidden = this.sheet.isRowHiddenByFilter(rowNum) || this.sheet.isRowHiddenByUser(rowNum);
      if (isHidden) {
        continue;
      }
      const value = this.sheet.getRange(rowNum, columnIndex + 1).getValue();
      values.push(value);
    }

    return values;
  }

  getRowIdsByTracking() {
    const trackingValues = this.getActiveValues('追跡番号');
    if (trackingValues.length === 0) {
      return [];
    }
    
    const trackingColumnIndex = this.getColumnIndex('追跡番号');
    const rowIdColumnIndex = this.getColumnIndex('行番号');
    const rowIds = [];
    
    // アクティブな行から取得した追跡番号のいずれかに一致する行の行IDを取得
    for (let i = 0; i < this.data.length; i++) {
      const rowTrackingNumber = String(this.data[i][trackingColumnIndex]);
      if (trackingValues.some(tv => String(tv) === rowTrackingNumber)) {
        rowIds.push(this.data[i][rowIdColumnIndex]);
      }
    }
    return rowIds;
  }
}
