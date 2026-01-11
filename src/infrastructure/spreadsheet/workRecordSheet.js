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

  /**
   * 納品プラン作成時のサマリを J-L 列に追記する
   * - J: 納品プラン（linkがあればHYPERLINK）
   * - K: ASIN
   * - L: 数量
   * @param {{inboundPlanId?: string, link?: string}} planResult
   * @param {Array<{asin: string, quantity: number}>} asinQuantities
   */
  appendInboundPlanSummary(planResult, asinQuantities) {
    const inboundPlanId = String((planResult && planResult.inboundPlanId) || '').trim();
    const link = String((planResult && planResult.link) || '').trim();
    const rows = Array.isArray(asinQuantities) ? asinQuantities : [];
    if (rows.length === 0) return;

    const lastRow = this.sheet.getLastRow();
    let newRow = lastRow + 1;

    for (const r of rows) {
      const asin = String((r && r.asin) || '').trim();
      const qty = Number((r && r.quantity) || 0);
      if (!asin || !qty || qty <= 0) continue;

      // J列: 納品プラン
      if (link) {
        const text = inboundPlanId || '納品プラン';
        this.sheet.getRange(newRow, 10).setFormula(`=HYPERLINK("${link}", "${text}")`);
      } else {
        this.sheet.getRange(newRow, 10).setValue(inboundPlanId);
      }

      // K-L列: ASIN, 数量
      this.sheet.getRange(newRow, 11).setValue(asin);
      this.sheet.getRange(newRow, 12).setValue(qty);

      newRow++;
    }
  }
}

