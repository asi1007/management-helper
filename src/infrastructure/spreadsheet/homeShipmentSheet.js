/* exported HomeShipmentSheet */

class HomeShipmentSheet extends BaseSheet {
  constructor(sheetName){
    super(sheetName, 3, 1);
    // BaseSheetのヘッダー行（row3）を列解決に使う
    this.headers = this._headersPrimary;
  }

  _getColumnIndex(columnName) {
    return this._getColumnIndexByName(columnName);
  }

  getValue(rowID, columnName) {
    const columnIndex = this._getColumnIndex(columnName);
    console.log(columnIndex);
    console.log(rowID);
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
    
    // データ検証: 有効な行番号が存在しない場合はエラーを投げる
    if (rowNumbers.length === 0) {
      throw new Error('選択された行に有効な行番号がありません。');
    }
    
    console.log(`取得した行番号: ${JSON.stringify(rowNumbers)}`);
    return rowNumbers;
  }

  getDefectReasonList() {
    // S列（19列目）から不良原因リストを読み込み
    const columnIndex = 18; // S列は19列目、0始まりなので18
    const lastRow = this.sheet.getLastRow();
    
    if (lastRow < 2) {
      return [];
    }
    
    // ヘッダー行を除いて、S列の値を取得（空でない値のみ）
    const values = this.sheet.getRange(2, 19, lastRow - 1, 1).getValues();
    const reasonList = values
      .map(row => row[0])
      .filter(value => value !== null && value !== undefined && value !== '');
    
    // 重複を除去
    const uniqueReasons = [...new Set(reasonList)];
    console.log(`不良原因リストを取得しました: ${JSON.stringify(uniqueReasons)}`);
    return uniqueReasons;
  }
}
