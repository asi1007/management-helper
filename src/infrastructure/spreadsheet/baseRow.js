/* exported BaseRow */

/**
 * BaseRow は「配列互換」の行オブジェクト。
 * - row[0] のような既存アクセスを壊さずに
 * - row.get('列名') で値取得できる
 */
class BaseRow extends Array {
  /**
   * @param {any[]} values
   * @param {(columnName: string) => number} columnIndexResolver
   * @param {number} rowNumber
   */
  constructor(values, columnIndexResolver, rowNumber) {
    super(...(Array.isArray(values) ? values : []));
    this._columnIndexResolver = columnIndexResolver;
    this.rowNumber = rowNumber;
  }

  /**
   * @param {string} columnName
   * @returns {any}
   */
  get(columnName) {
    const idx = this._columnIndexResolver(columnName);
    const v = this[idx];
    return typeof v === 'string' ? v.trim() : v;
  }
}



