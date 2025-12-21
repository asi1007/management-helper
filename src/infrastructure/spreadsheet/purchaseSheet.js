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

  filter(trackingNumbers) {
    const trackingColumnIndex = this.setting.get('追跡番号');
    const rowNumbers = [];
    const filteredData = [];
    
    for (let i = 0; i < this.data.length; i++) {
      const rowTrackingNumber = String(this.data[i][trackingColumnIndex]);
      if (trackingNumbers.some(tn => String(tn) === rowTrackingNumber)) {
        // データ配列は0始まり、行番号は1始まり、ヘッダーが1行あるため +2
        rowNumbers.push(i + 2);
        filteredData.push(this.data[i]);
      }
    }
    
    this.rowNumbers = rowNumbers;
    this.data = filteredData;
    console.log(`追跡番号でフィルタリング: ${rowNumbers.length}行が見つかりました`);
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
