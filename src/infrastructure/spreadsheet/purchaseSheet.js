/* exported PurchaseSheet */

class PurchaseSheet extends BaseSheet {
  constructor(sheetID, sheetName, setting){
    super(sheetID, sheetName);
    this.setting = setting;
    this.rowNumbers = [];
  }

  setRowNumbers(rowNumbers){
    this.rowNumbers = rowNumbers;
  }

  filter(columnName, values) {
    console.log(`Filtering column "${columnName}" with values: ${JSON.stringify(values)}`);
    const columnIndex = this.setting.get(columnName);
    const rowNumbers = [];
    const filteredData = [];
    
    for (let i = 0; i < this.data.length; i++) {
      const rowValue = String(this.data[i][columnIndex]);
      if (values.some(v => String(v) === rowValue)) {
        // データ配列は0始まり、行番号は1始まり、ヘッダーが1行あるため +2
        rowNumbers.push(i + 2);
        filteredData.push(this.data[i]);
      }
    }
    
    this.rowNumbers = rowNumbers;
    this.data = filteredData;
    console.log(`${columnName}でフィルタリング: ${rowNumbers.length}行が見つかりました`);
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


}
