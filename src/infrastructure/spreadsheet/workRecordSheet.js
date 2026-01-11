/* exported WorkRecordSheet */

class WorkRecordSheet extends BaseSheet {
  constructor(sheetName) {
    super(sheetName);
  }

  /**
   * 指定列の「最後に値が入っている行」を取得する（空行は無視）
   * @param {number} columnNum 1-based
   * @returns {number} last row number (1-based). 見つからなければ0
   */
  _getLastNonEmptyRowInColumn_(columnNum) {
    const maxRows = this.sheet.getMaxRows();
    const chunkSize = 500;
    for (let end = maxRows; end >= 1; end -= chunkSize) {
      const start = Math.max(1, end - chunkSize + 1);
      const values = this.sheet.getRange(start, columnNum, end - start + 1, 1).getValues();
      for (let i = values.length - 1; i >= 0; i--) {
        const v = values[i][0];
        if (v !== '' && v !== null && v !== undefined) {
          return start + i;
        }
      }
    }
    return 0;
  }

  /**
   * 追記する行番号を決める。
   * - J列が「運用上の最後尾」だが、appendRecord(A〜)はJを埋めないためA列も考慮して上書きを防ぐ
   * @returns {number} next row number (1-based)
   */
  _getNextAppendRow_() {
    const lastJ = this._getLastNonEmptyRowInColumn_(10); // J
    const lastA = this._getLastNonEmptyRowInColumn_(1);  // A
    return Math.max(lastJ, lastA) + 1;
  }

  appendRecord(asin, purchaseDate, status, timestamp, quantity = null, reason = null, comment = null) {
    const newRow = this._getNextAppendRow_();
    
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

    let newRow = this._getNextAppendRow_();

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

