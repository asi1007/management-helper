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

    // J列の「最後に値が入っている行」を基準に追記する
    // （J列は納品プランサマリの主キー列）
    const maxRow = this.sheet.getLastRow();
    let lastJ = 0;
    if (maxRow > 0) {
      const jValues = this.sheet.getRange(1, 10, maxRow, 1).getValues(); // J1:JmaxRow
      for (let i = jValues.length - 1; i >= 0; i--) {
        const v = jValues[i][0];
        if (v !== '' && v !== null && v !== undefined) {
          lastJ = i + 1; // 1-based row
          break;
        }
      }
    }
    // ヘッダー行を潰さないため、最低でも2行目以降に書く
    let newRow = Math.max(2, lastJ + 1);
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    for (const r of rows) {
      const asin = String((r && r.asin) || '').trim();
      const qty = Number((r && r.quantity) || 0);
      if (!asin || !qty || qty <= 0) continue;

      // I列: 今日の日付
      this.sheet.getRange(newRow, 9).setValue(today);

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

