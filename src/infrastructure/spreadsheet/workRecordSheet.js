/* exported WorkRecordSheet */

class WorkRecordSheet extends BaseSheet {
  constructor(sheetID, sheetName) {
    super(sheetID, sheetName);
  }

  appendRecord(asin, purchaseDate, status, timestamp) {
    const lastRow = this.sheet.getLastRow();
    const newRow = lastRow + 1;
    
    // ASIN, 購入日, ステータス, 時刻の順で記入
    this.sheet.getRange(newRow, 1).setValue(asin);
    this.sheet.getRange(newRow, 2).setValue(purchaseDate);
    this.sheet.getRange(newRow, 3).setValue(status);
    this.sheet.getRange(newRow, 4).setValue(timestamp);
    
    console.log(`作業記録を追加しました: ASIN=${asin}, 購入日=${purchaseDate}, ステータス=${status}, 時刻=${timestamp}`);
  }
}

