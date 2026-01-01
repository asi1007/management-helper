/* exported createInspectionSheetFromPurchaseRowsIfNeeded */

function createInspectionSheetFromPurchaseRowsIfNeeded(purchaseRows) {
  const config = getEnvConfig();

  if (!Array.isArray(purchaseRows) || purchaseRows.length === 0) {
    return null;
  }

  const asins = purchaseRows
    .map(r => {
      try { return String(r.get("ASIN") || '').trim(); } catch (e) { return ''; }
    })
    .filter(Boolean);
  const repo = new InspectionMasterSpreadsheetRepository(
    config.INSPECTION_MASTER_SHEET_ID,
    Number(config.INSPECTION_MASTER_SHEET_GID)
  );
  const masterMap = repo.findByAsins(asins);
  if (masterMap.size === 0) {
    return null;
  }

  // マッチしたものだけ検品シートに載せる
  const matched = [];
  for (const r of purchaseRows) {
    let asin = '';
    try { asin = String(r.get("ASIN") || '').trim(); } catch (e) { asin = ''; }
    const masterItem = masterMap.get(asin);
    if (!masterItem) continue;

    let orderNo = '';
    try { orderNo = r.get("注文番号") || ''; } catch (e) {}

    let quantity = 0;
    try { quantity = Number(r.get("数量") || 0) || 0; } catch (e) { quantity = 0; }

    let productName = '';
    try { productName = r.get("商品名") || ''; } catch (e) {}
    let imageUrl = '';
    try { imageUrl = r.get("商品写真") || ''; } catch (e) {}

    const keepa = _getKeepaProductSnapshot(asin);
    matched.push({
      asin,
      orderNo,
      productName: productName || (keepa ? keepa.title : ''),
      imageUrl: imageUrl || (keepa ? keepa.imageUrl : ''),
      quantity,
      inspectionPoint: masterItem.inspectionPoint || ''
    });
  }

  if (matched.length === 0) {
    return null;
  }

  const planName = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd') + '-検品';
  const fileId = DriveApp.getFileById(config.INSPECTION_TEMPLATE_SHEET_ID).makeCopy(planName).getId();
  const ss = SpreadsheetApp.openById(fileId);
  const sheet = ss.getSheetById(Number(config.INSPECTION_TEMPLATE_SHEET_GID)) || ss.getActiveSheet();

  // 指定: 9,14,19,24... 行 / C:注文番号, D:商品名, E:商品写真, G:数量, H:検品箇所
  const startRow = 9;
  const step = 5;
  for (let i = 0; i < matched.length; i++) {
    const targetRow = startRow + (i * step);
    const item = matched[i];

    sheet.getRange(targetRow, 3).setValue(item.orderNo);          // C
    sheet.getRange(targetRow, 4).setValue(item.productName);      // D
    if (item.imageUrl) {
      sheet.getRange(targetRow, 5).setFormula(`=IMAGE("${item.imageUrl}")`); // E
    }
    sheet.getRange(targetRow, 7).setValue(item.quantity);         // G
    sheet.getRange(targetRow, 8).setValue(item.inspectionPoint);  // H
  }

  return `https://docs.google.com/spreadsheets/d/${fileId}/edit`;
}

function _getKeepaProductSnapshot(asin) {
  if (!asin) return null;

  const config = getEnvConfig();
  const url = `https://api.keepa.com/product?key=${config.KEEPA_API_KEY}&domain=5&asin=${asin}`;

  try {
    const response = UrlFetchApp.fetch(url, { method: 'get', muteHttpExceptions: true });
    const json = JSON.parse(response.getContentText());
    if (json.error || !json.products || json.products.length === 0) {
      return null;
    }
    const product = json.products[0];
    const title = product.title || '';
    const imagesCSV = product.imagesCSV || '';
    const firstImageFile = imagesCSV ? imagesCSV.split(',')[0] : '';
    const imageUrl = firstImageFile ? `https://images-na.ssl-images-amazon.com/images/I/${firstImageFile}._SL100_.jpg` : '';
    return { title, imageUrl };
  } catch (e) {
    console.warn(`Keepa fetch failed for ASIN ${asin}: ${e.message}`);
    return null;
  }
}


