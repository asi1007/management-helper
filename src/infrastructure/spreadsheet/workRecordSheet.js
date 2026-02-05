/* exported WorkRecordSheet */

class WorkRecordSheet extends BaseSheet {
  constructor(sheetName) {
    super(sheetName);
  }

  appendRecord(asin, purchaseDate, status, timestamp, quantity = null, reason = null, comment = null, orderNumber = null) {
    // A列の最後に値が入っている行を基準にする（納品プラン記録の行を除外）
    const maxRow = this.sheet.getLastRow();
    let lastA = 0;
    if (maxRow > 0) {
      const aValues = this.sheet.getRange(1, 1, maxRow, 1).getValues(); // A1:AmaxRow
      for (let i = aValues.length - 1; i >= 0; i--) {
        const v = aValues[i][0];
        if (v !== '' && v !== null && v !== undefined) {
          lastA = i + 1; // 1-based row
          break;
        }
      }
    }
    // ヘッダー行を潰さないため、最低でも2行目以降に書く
    const newRow = Math.max(2, lastA + 1);
    
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
    
    // 注文番号が指定されている場合は追加
    if (orderNumber !== null && orderNumber !== '') {
      this.sheet.getRange(newRow, 8).setValue(orderNumber);
    }
    
    console.log(`作業記録を追加しました: ASIN=${asin}, 購入日=${purchaseDate}, ステータス=${status}, 時刻=${timestamp}, 数量=${quantity}, 原因=${reason}, コメント=${comment}, 注文番号=${orderNumber}`);
  }

  /**
   * 納品プラン作成時のサマリを（右に2列ずらして）K-O 列に追記する
   * - K: プラン作成日（今日の日付）
   * - L: 納品プラン（linkがあればHYPERLINK）
   * - M: ASIN
   * - N: 数量
   * - O: 注文番号
   * @param {{inboundPlanId?: string, link?: string}} planResult
   * @param {Array<{asin: string, quantity: number, orderNumber?: string}>} asinRecords
   */
  appendInboundPlanSummary(planResult, asinRecords) {
    const inboundPlanId = String((planResult && planResult.inboundPlanId) || '').trim();
    const link = String((planResult && planResult.link) || '').trim();
    const rows = Array.isArray(asinRecords) ? asinRecords : [];
    if (rows.length === 0) return;

    // L列の「最後に値が入っている行」を基準に追記する
    // （L列は納品プランサマリの主キー列）
    const maxRow = this.sheet.getLastRow();
    let lastL = 0;
    if (maxRow > 0) {
      const lValues = this.sheet.getRange(1, 12, maxRow, 1).getValues(); // L1:LmaxRow
      for (let i = lValues.length - 1; i >= 0; i--) {
        const v = lValues[i][0];
        if (v !== '' && v !== null && v !== undefined) {
          lastL = i + 1; // 1-based row
          break;
        }
      }
    }
    // ヘッダー行を潰さないため、最低でも2行目以降に書く
    let newRow = Math.max(2, lastL + 1);
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    for (const r of rows) {
      const asin = String((r && r.asin) || '').trim();
      const qty = Number((r && r.quantity) || 0);
      const orderNo = String((r && r.orderNumber) || '').trim();
      if (!asin || !qty || qty <= 0) continue;

      // K列: 今日の日付（プラン作成日）
      this.sheet.getRange(newRow, 11).setValue(today);

      // L列: 納品プラン
      if (link) {
        const text = inboundPlanId || '納品プラン';
        this.sheet.getRange(newRow, 12).setFormula(`=HYPERLINK("${link}", "${text}")`);
      } else {
        this.sheet.getRange(newRow, 12).setValue(inboundPlanId);
      }

      // M-N列: ASIN, 数量
      this.sheet.getRange(newRow, 13).setValue(asin);
      this.sheet.getRange(newRow, 14).setValue(qty);

      // O列: 注文番号
      if (orderNo) {
        this.sheet.getRange(newRow, 15).setValue(orderNo);
      }

      newRow++;
    }
  }
}

