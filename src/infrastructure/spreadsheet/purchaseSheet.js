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
