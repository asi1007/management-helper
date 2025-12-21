/* exported HomeShipmentSheet */

class HomeShipmentSheet {
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
