/* exported HomeShipmentSheet */

class HomeShipmentSheet extends BaseSheet {
  constructor(sheetID, sheetName){
    super(sheetID, sheetName);
    this.headers = this.data[1]; 
  }

  _getColumnIndex(columnName) {
    const index = this.headers.indexOf(columnName);
    if (index === -1) {
      throw new Error(`列 "${columnName}" が見つかりません`);
    }
    return index;
  }

  getValue(rowID, columnName) {
    const columnIndex = this._getColumnIndex(columnName);
    return this.sheet.getRange(rowID, columnIndex + 1).getValue();
  }

  getValues(columnName) {
    const columnIndex = this._getColumnIndex(columnName);
    const values = this.data.map(row => row[columnIndex]);
    console.log(`Column "${columnName}" values (first 5): ${JSON.stringify(values.slice(0, 5))}... (total ${values.length})`);
    return values;
  }

  getRowIdsByTracking() {
    activeRows = this.getActiveRowData();
    const trackingValues = getActiveValues('追跡番号');
    
    for (let i = 0; i < this.data.length; i++) {
      rowIds = tracking ("行番号");
      if (String(this.data[i][trackingColumnIndex]) === String(trackingNumber)) {
        rowIds.push(this.data[i][rowIdColumnIndex]);
      }
    }
    return rowIds;
  }

  getActiveRowNumbers() {
    const activeData = this.getActiveRowData();
    const rowNumberColumnIndex = this._getColumnIndex("行番号");
    const rowNumbers = activeData.map(row => row[rowNumberColumnIndex]).filter(rn => rn !== null && rn !== undefined && rn !== '');
    console.log(`取得した行番号: ${JSON.stringify(rowNumbers)}`);
    return rowNumbers;
  }
}
