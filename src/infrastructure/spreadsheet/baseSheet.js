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
    const headerRaw = this.sheet.getRange(this.headerRow, startColumn, 1, 100).getValues()[0] || [];
    this._headersPrimaryRaw = headerRaw;
    this._headersPrimary = headerRaw.map(h => String(h ?? '').trim());
    this._headerIndexMap = new Map();
    for (let i = 0; i < this._headersPrimary.length; i++) {
      const key = this._headersPrimary[i];
      if (!key) continue;
      if (!this._headerIndexMap.has(key)) {
        this._headerIndexMap.set(key, i);
      }
    }
    
    // データ範囲を計算（startRowから最後の行まで、100列分）
    const numRows = Math.max(0, this.lastRow - this.startRow + 1);
    const raw = numRows > 0 ? this.sheet.getRange(this.startRow, startColumn, numRows, 100).getValues() : [];

    this.data = raw.map((values, i) => new BaseRow(values, (name) => this._getColumnIndexByName(name), this.startRow + i));
    // getActiveRowData() が this.data を選択行で上書きするため、全行データも保持しておく
    this.allData = this.data;
  }

  _getColumnIndexByName(columnName) {
    const key = String(columnName ?? '').trim();
    const idx = this._headerIndexMap.get(key);
    if (idx !== undefined) {
      return idx;
    }
    throw new Error(`列 "${key}" が見つかりません。ヘッダー: ${JSON.stringify(this._headersPrimary.filter(Boolean))}`);
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

  /**
   * columnName列へ、各行に対して関数で計算した値を書き込む。
   * - valueFunc(row, index) が返す値:
   *   - そのまま setValue する値
   *   - {type:'formula', value:'=...'} なら setFormula
   *   - null/undefined ならスキップ
   */
  writeColumnByFunc(columnName, valueFunc) {
    const columnNum = this._getColumnIndexByName(columnName) + 1;
    let successCount = 0;

    for (let i = 0; i < this.data.length; i++) {
      const row = this.data[i];
      const rowNum = row && row.rowNumber ? row.rowNumber : null;
      if (!rowNum) continue;

      const value = valueFunc(row, i);
      if (value === null || value === undefined) continue;

      this.writeCell(rowNum, columnNum, value);
      successCount++;
    }

    console.log(`${columnName}を${successCount}行に書き込みました(by func)`);
    return successCount;
  }
}
