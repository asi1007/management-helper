/* exported LabelItem */

class LabelItem {
  /**
   * @param {string} sku
   * @param {number} quantity
   */
  constructor(sku, quantity) {
    this.sku = String(sku || '').trim();
    this.quantity = Number(quantity || 0) || 0;

    if (!this.sku) {
      throw new Error('SKUが空です');
    }
    if (!Number.isFinite(this.quantity) || this.quantity <= 0) {
      throw new Error(`数量が不正です: ${quantity}`);
    }
  }

  /**
   * Downloader.downloadLabels() の mskuQuantities 形式へ変換
   * @returns {{msku: string, quantity: number}}
   */
  toMskuQuantity() {
    return { msku: this.sku, quantity: this.quantity };
  }
}


