/* exported InspectionMasterCatalog */

class InspectionMasterCatalog {
  /**
   * @param {Map<string, InspectionMasterItem>} itemsByAsin
   */
  constructor(itemsByAsin) {
    this._itemsByAsin = itemsByAsin || new Map();
  }

  /**
   * @param {string[]} asins
   * @returns {InspectionMasterCatalog}
   */
  filterByAsins(asins) {
    const set = new Set((asins || []).map(a => String(a || '').trim()).filter(Boolean));
    const next = new Map();
    for (const [asin, item] of this._itemsByAsin.entries()) {
      if (set.has(asin)) {
        next.set(asin, item);
      }
    }
    return new InspectionMasterCatalog(next);
  }

  /**
   * @param {string} asin
   * @returns {boolean}
   */
  has(asin) {
    return this._itemsByAsin.has(String(asin || '').trim());
  }

  /**
   * @param {string} asin
   * @returns {InspectionMasterItem|null}
   */
  get(asin) {
    return this._itemsByAsin.get(String(asin || '').trim()) || null;
  }

  /**
   * @returns {number}
   */
  size() {
    return this._itemsByAsin.size;
  }

  /**
   * @returns {string[]}
   */
  asins() {
    return Array.from(this._itemsByAsin.keys());
  }
}


