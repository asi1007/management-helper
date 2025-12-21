/* exported BaseSheet */

class BaseSheet {
  constructor(sheetID, sheetName){
    this.sheet = SpreadsheetApp.openById(sheetID).getSheetByName(sheetName);
    this.lastRow = this.sheet.getLastRow();
    this.data = this.sheet.getRange(2, 1, this.lastRow, 100).getValues();
  }

  getActiveRowData(){
    const selectedRowNumbers = this._getSelectedRowNumbers(this.sheet);
    const sortedRowNumbers = Array.from(selectedRowNumbers).sort((a, b) => a - b);

    const selectedRows = [];
    const finalRowNumbers = [];

    for (const rowNum of sortedRowNumbers) {
      const isHidden = this.sheet.isRowHiddenByFilter(rowNum) || this.sheet.isRowHiddenByUser(rowNum);
      console.log(`行番号 ${rowNum}: フィルタ非表示=${this.sheet.isRowHiddenByFilter(rowNum)}, 手動非表示=${this.sheet.isRowHiddenByUser(rowNum)}, 判定=${isHidden ? 'スキップ' : '対象'}`);
      if (isHidden) {
        continue;
      }

      // データ配列は0始まり、行番号は1始まり、ヘッダーが1行あるため -2
      const dataIndex = rowNum - 2;
      if (dataIndex < 0 || dataIndex >= this.data.length) {
        continue;
      }

      const rowData = this.data[dataIndex];
      selectedRows.push(rowData);
      finalRowNumbers.push(rowNum);
    }

    // インスタンスの状態を更新
    this.data = selectedRows;
    if (this.rowNumbers !== undefined) {
      this.rowNumbers = finalRowNumbers;
    }

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
