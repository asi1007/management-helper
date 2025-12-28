/* exported BaseSheet */

class BaseSheet {
  constructor(sheetName, startRow = 1, startColumn = 1){
    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    this.sheet = spreadsheet.getSheetByName(sheetName);
    if (!this.sheet) {
      throw new Error(`シート "${sheetName}" が見つかりません`);
    }
    this.lastRow = this.sheet.getLastRow();
    this.headerRow = startRow;
    this.startRow = startRow + 1;
    this.startColumn = startColumn;
    
    // 列名->index 解決に使うヘッダー（startRow行のみ）
    this._headersPrimary = this.sheet.getRange(this.headerRow, startColumn, 1, 100).getValues()[0] || [];
    
    // データ範囲を計算（startRowから最後の行まで、100列分）
    const numRows = Math.max(0, this.lastRow - this.startRow + 1);
    const raw = numRows > 0 ? this.sheet.getRange(this.startRow, startColumn, numRows, 100).getValues() : [];

    this.data = raw.map((values, i) => new BaseRow(values, (name) => this._getColumnIndexByName(name), this.startRow + i));
  }

  _getColumnIndexByName(columnName) {
    const idxPrimary = this._headersPrimary.indexOf(columnName);
    if (idxPrimary !== -1) {
      return idxPrimary;
    }
    throw new Error(`列 "${columnName}" が見つかりません`);
  }

  getActiveRowData(){
    const selectedRowNumbers = this._getSelectedRowNumbers(this.sheet);
    const sortedRowNumbers = Array.from(selectedRowNumbers).sort((a, b) => a - b);
    const selectedRows = [];
    const finalRowNumbers = [];
    const skippedRows = [];

    for (const rowNum of sortedRowNumbers) {
      const isHidden = this.sheet.isRowHiddenByFilter(rowNum) || this.sheet.isRowHiddenByUser(rowNum);
      console.log(`行番号 ${rowNum}: フィルタ非表示=${this.sheet.isRowHiddenByFilter(rowNum)}, 手動非表示=${this.sheet.isRowHiddenByUser(rowNum)}, 判定=${isHidden ? 'スキップ' : '対象'}`);
      if (isHidden) {
        skippedRows.push({row: rowNum, reason: '非表示'});
        continue;
      }

      // データ配列は0始まり、行番号は1始まり、startRowから始まるため
      const dataIndex = rowNum - this.startRow;
      if (dataIndex < 0 || dataIndex >= this.data.length) {
        skippedRows.push({row: rowNum, reason: `データ範囲外（開始行: ${this.startRow}, データ行数: ${this.data.length})`});
        continue;
      }

      const rowData = this.data[dataIndex];

      selectedRows.push(rowData);
      finalRowNumbers.push(rowNum);
    }

    // データ検証: 選択された行が存在しない場合はエラーを投げる
    if (selectedRows.length === 0) {
      const skippedInfo = skippedRows.length > 0 
        ? `\nスキップされた行: ${skippedRows.map(s => `行${s.row}(${s.reason})`).join(', ')}`
        : '';
      throw new Error(`選択された行がありません。すべての選択行が非表示またはデータ範囲外です。${skippedInfo}`);
    }

    // インスタンスの状態を更新
    this.data = selectedRows;
    this.rowNumbers = finalRowNumbers;

    console.log(`選択された行: [${finalRowNumbers.join(', ')}]`);

    return selectedRows;
  }

  _getSelectedRowNumbers(activeSheet) {
    const selectedRowNumbers = new Set();
    
    // 複数の範囲が選択されている場合
    const activeRangeList = activeSheet.getActiveRangeList();
    if (activeRangeList && activeRangeList.getRanges().length > 0) {
      const ranges = activeRangeList.getRanges();
      for (const range of ranges) {
        this._addSelectedRowNumbers(selectedRowNumbers, range);
      }
    } else {
      // 単一の範囲が選択されている場合
      const activeRange = activeSheet.getActiveRange();
      if (activeRange) {
        this._addSelectedRowNumbers(selectedRowNumbers, activeRange);
      }
    }
    
    console.log(`Selected row numbers: ${Array.from(selectedRowNumbers).join(', ') || '(なし)'}`);
    return selectedRowNumbers;
  }

  _addSelectedRowNumbers(selectedRowNumbers, activeRange){
      const startRow = activeRange.getRow();
      const numRows = activeRange.getNumRows();
      console.log(`Adding rows: rownums${startRow} to ${startRow + numRows - 1}`);
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
