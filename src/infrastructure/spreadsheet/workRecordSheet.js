/* exported WorkRecordSheet */

class WorkRecordSheet extends BaseSheet {
  constructor(sheetName) {
    super(sheetName);
  }

  appendRecord(asin, purchaseDate, status, timestamp, quantity = null, reason = null, comment = null) {
    const lastRow = this.sheet.getLastRow();
    const newRow = lastRow + 1;
    
    // ASIN, 購入日, ステータス, 時刻の順で記入
    this.sheet.getRange(newRow, 1).setValue(asin);
    this.sheet.getRange(newRow, 2).setValue(purchaseDate);
    this.sheet.getRange(newRow, 3).setValue(status);
    this.sheet.getRange(newRow, 4).setValue(timestamp);
    
    // 数量が指定されている場合は追加
    if (quantity !== null) {
      this.sheet.getRange(newRow, 5).setValue(quantity);
    }
    
    // 原因が指定されている場合は追加
    if (reason !== null) {
      this.sheet.getRange(newRow, 6).setValue(reason);
    }
    
    // コメントが指定されている場合は追加
    if (comment !== null && comment !== '') {
      this.sheet.getRange(newRow, 7).setValue(comment);
    }
    
    console.log(`作業記録を追加しました: ASIN=${asin}, 購入日=${purchaseDate}, ステータス=${status}, 時刻=${timestamp}, 数量=${quantity}, 原因=${reason}, コメント=${comment}`);
  }
}

