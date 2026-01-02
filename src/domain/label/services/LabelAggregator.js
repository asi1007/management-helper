/* exported LabelAggregator */

class LabelAggregator {
  /**
   * BaseRow[] から SKU 数量を集計して LabelItem[] を返す
   * @param {any[]} rows
   * @returns {LabelItem[]}
   */
  aggregate(rows) {
    const map = new Map();

    for (const row of rows || []) {
      const sku = String(row.get("SKU") || '').trim();
      const quantity = Number(row.get("購入数") || 0) || 0;

      if (!sku || quantity <= 0) continue;
      map.set(sku, (map.get(sku) || 0) + quantity);
    }

    const items = Array.from(map.entries()).map(([sku, qty]) => new LabelItem(sku, qty));
    if (items.length === 0) {
      throw new Error('有効なSKUがありません');
    }
    return items;
  }
}


