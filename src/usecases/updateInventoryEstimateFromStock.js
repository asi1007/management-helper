/* exported updateInventoryEstimateFromStockSheet */

/**
 * stockシートのヘッダー行から「ASIN」列と「販売可能」を含む列を特定し、
 * 仕入管理シート（PurchaseSheet）の各ASINについて、下の行から順に:
 * 1) 在庫数推測値 = min(購入数, 販売可能在庫数(temp))
 * 2) 販売可能在庫数(temp) = 販売可能在庫数(temp) - 在庫数推測値
 * 3) 在庫数推測値 == 0 のとき、ステータス推測値 = 在庫無し
 */
function updateInventoryEstimateFromStockSheet() {
  const config = getEnvConfig();
  const purchase = new PurchaseSheet(config.PURCHASE_SHEET_NAME);

  const stockMap = _loadAsinToAvailableStockFromStockSheet_('stock');
  console.log(`[在庫推測] stock loaded: asins=${stockMap.size}`);

  const qtyColName = '購入数';
  const asinColName = 'ASIN';
  const statusColName = 'ステータス';
  const invEstColName = '在庫数推測値';
  const statusEstColName = 'ステータス推測値';

  const invEstCol = purchase._getColumnIndexByName(invEstColName) + 1;
  const statusEstCol = purchase._getColumnIndexByName(statusEstColName) + 1;

  // 全行をASINでグルーピングし、行番号降順（下から）で処理
  const groups = new Map(); // asin -> BaseRow[]
  const allRows = Array.isArray(purchase.allData) ? purchase.allData : purchase.data;
  for (const row of allRows) {
    const asin = String(row.get(asinColName) || '').trim();
    if (!asin) continue;
    const status = String(row.get(statusColName) || '').trim();
    // 更新対象: ステータスが在庫あり の行のみ
    if (status !== '在庫あり') continue;
    if (!groups.has(asin)) groups.set(asin, []);
    groups.get(asin).push(row);
  }

  let written = 0;
  let statusChanged = 0;
  for (const [asin, rows] of groups.entries()) {
    rows.sort((a, b) => (b.rowNumber || 0) - (a.rowNumber || 0));

    let temp = Number(stockMap.get(asin) || 0);
    if (!isFinite(temp) || temp < 0) temp = 0;

    for (const row of rows) {
      const rowNum = row.rowNumber;
      const purchaseQty = Number(row.get(qtyColName) || 0) || 0;

      const invEst = Math.min(purchaseQty, temp);
      purchase.writeCell(rowNum, invEstCol, invEst);
      written++;

      temp = Math.max(0, temp - invEst);

      if (invEst === 0) {
        purchase.writeCell(rowNum, statusEstCol, '在庫無し');
        statusChanged++;
      }

      console.log(`[在庫推測] asin=${asin} row=${rowNum} 購入数=${purchaseQty} temp(after)=${temp} 在庫数推測値=${invEst}${invEst === 0 ? ' -> 在庫無し' : ''}`);
    }
  }

  console.log(`[在庫推測] 完了: written=${written}, statusChanged=${statusChanged}, asinsProcessed=${groups.size}`);
}

function _loadAsinToAvailableStockFromStockSheet_(sheetName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) throw new Error(`stockシート "${sheetName}" が見つかりません`);

  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if (lastRow < 2 || lastCol < 1) return new Map();

  // 1行目のヘッダーからASIN列と販売可能列を特定
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  let asinCol = -1;
  let availableCol = -1;
  for (let i = 0; i < headers.length; i++) {
    const h = String(headers[i] || '').trim();
    if (h === 'ASIN' || h === 'asin') asinCol = i;
    if (h.indexOf('販売可能') !== -1) availableCol = i;
  }
  if (asinCol === -1) throw new Error(`stockシートにASIN列が見つかりません。headers=${JSON.stringify(headers)}`);
  if (availableCol === -1) throw new Error(`stockシートに販売可能列が見つかりません。headers=${JSON.stringify(headers)}`);
  console.log(`[在庫推測] stockシート列: ASIN=${asinCol + 1}列目, 販売可能=${availableCol + 1}列目`);

  const values = sheet.getRange(2, 1, lastRow - 1, lastCol).getValues();
  const map = new Map();
  for (const r of values) {
    const asin = String(r[asinCol] || '').trim();
    if (!asin) continue;
    const available = Number(r[availableCol] || 0);
    if (!isFinite(available)) continue;
    map.set(asin, available);
  }
  return map;
}

