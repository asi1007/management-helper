/* exported createInspectionSheetFromPurchaseRowsIfNeeded_ */

function createInspectionSheetFromPurchaseRowsIfNeeded_(purchaseRows) {
  const config = getEnvConfig();
  console.log(`[検品] createInspectionSheetFromPurchaseRowsIfNeeded: purchaseRows=${(purchaseRows || []).length}`);
  const asins = purchaseRows
    .map(r => {
      try { return String(r.get("ASIN") || '').trim(); } catch (e) { return ''; }
    })
    .filter(Boolean);
  console.log(`[検品] 対象ASIN数=${asins.length}`);
  const repo = new InspectionMasterRepo(
    config.INSPECTION_MASTER_SHEET_ID,
    Number(config.INSPECTION_MASTER_SHEET_GID)
  );
  const catalog = repo.load().filterByAsins(asins);
  if (catalog.size() === 0) {
    console.log('[検品] マスタ一致なし -> 検品シート作成スキップ');
    return null;
  }
  console.log(`[検品] マスタ一致ASIN数=${catalog.size()}`);

  // マッチしたものだけ検品シートに載せる
  const matched = [];
  for (const r of purchaseRows) {
    let asin = '';
    try { asin = String(r.get("ASIN") || '').trim(); } catch (e) { asin = ''; }
    const masterItem = catalog.get(asin);
    if (!masterItem) continue;

    let orderNo = '';
    try { orderNo = r.get("注文番号") || ''; } catch (e) {}

    let quantity = 0;
    try { quantity = Number(r.get("購入数") || 0) || 0; } catch (e) { quantity = 0; }

    matched.push({
      asin,
      orderNo,
      productName: masterItem.productName || '',
      quantity,
      inspectionPoint: masterItem.inspectionPoint || '',
      detailInstructionUrl: masterItem.detailInstructionUrl || ''
    });
  }

  if (matched.length === 0) {
    console.log('[検品] マスタ一致はあるが、書き込み対象0件 -> 検品シート作成スキップ');
    return null;
  }
  console.log(`[検品] 検品シート書き込み対象件数=${matched.length}`);

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
    // E: 商品写真（InstructionSheetと同じ方式: Keepa -> Amazon画像URL -> blob -> insertImage）
    const imageUrl = _getProductImageUrl(item.asin);
    if (imageUrl) {
      try {
        const blob = UrlFetchApp.fetch(imageUrl).getBlob();
        sheet.insertImage(blob, 5, targetRow);
      } catch (e) {
        console.warn(`[検品] 画像取得/挿入に失敗: ASIN=${item.asin}, url=${imageUrl}, error=${e.message}`);
      }
    }
    sheet.getRange(targetRow, 7).setValue(item.quantity);         // G
    sheet.getRange(targetRow, 8).setValue(item.inspectionPoint);  // H
  }

  _appendDetailInstructionSheets(ss, matched);

  const editUrl = `https://docs.google.com/spreadsheets/d/${fileId}/edit`;
  const xlsxUrl = `https://docs.google.com/spreadsheets/d/${fileId}/export?format=xlsx`;
  console.log(`[検品] 検品シート作成完了: edit=${editUrl}`);
  console.log(`[検品] 検品シート(xlsx): ${xlsxUrl}`);
  return xlsxUrl;
}

function _appendDetailInstructionSheets(targetSpreadsheet, matchedItems) {
  const srcSheetName = '検品詳細指示書';
  const items = (matchedItems || []).filter(it => it && it.detailInstructionUrl);
  if (items.length === 0) {
    console.log('[検品] 詳細指示書URLなし -> 詳細指示書シート追加スキップ');
    return;
  }

  console.log(`[検品] 詳細指示書URLあり件数=${items.length} -> シートコピー開始`);

  for (const item of items) {
    const parsed = _parseSpreadsheetUrl(item.detailInstructionUrl);
    if (!parsed || !parsed.spreadsheetId) {
      console.warn(`[検品] 詳細指示書URLを解析できません: ASIN=${item.asin}, url=${item.detailInstructionUrl}`);
      continue;
    }

    try {
      const file = DriveApp.getFileById(parsed.spreadsheetId);
      const mimeType = file.getMimeType();

      if (mimeType !== 'application/vnd.google-apps.spreadsheet') {
        const isExcel = mimeType.includes('spreadsheetml') || mimeType.includes('excel');
        const formatHint = isExcel ? 'xlsx/Excel形式です。Googleスプレッドシートに変換してください' : `MIMEタイプ: ${mimeType}`;
        console.warn(`[検品] 詳細指示書がGoogleスプレッドシート形式ではありません: ASIN=${item.asin}, ${formatHint}`);
        continue;
      }

      const srcSs = SpreadsheetApp.openById(parsed.spreadsheetId);
      const srcSheet =
        (parsed.gid ? srcSs.getSheetById(Number(parsed.gid)) : null) ||
        srcSs.getSheetByName(srcSheetName) ||
        srcSs.getActiveSheet();

      if (!srcSheet) {
        console.warn(`[検品] コピー元シートが見つかりません: ASIN=${item.asin}, spreadsheetId=${parsed.spreadsheetId}, gid=${parsed.gid}`);
        continue;
      }

      const copied = srcSheet.copyTo(targetSpreadsheet);
      const desiredName = _makeUniqueSheetName(targetSpreadsheet, `${srcSheetName}_${item.productName}`);
      copied.setName(desiredName);
      console.log(`[検品] 詳細指示書シート追加: ASIN=${item.asin}, name=${desiredName}`);
    } catch (e) {
      console.warn(`[検品] 詳細指示書シート追加に失敗: ASIN=${item.asin}, url=${item.detailInstructionUrl}, error=${e.message}`);
      try { SpreadsheetApp.flush(); } catch (_) {}
    }
  }
}

function _parseSpreadsheetUrl(url) {
  const s = String(url || '').trim();
  if (!s) return null;
  const m = s.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
  const spreadsheetId = m ? m[1] : null;
  const gidMatch = s.match(/[?#&]gid=([0-9]+)/);
  const gid = gidMatch ? gidMatch[1] : null;
  return { spreadsheetId, gid };
}

function _makeUniqueSheetName(spreadsheet, baseName) {
  const safe = String(baseName || '').trim().slice(0, 90) || 'Sheet';
  const existing = new Set(spreadsheet.getSheets().map(sh => sh.getName()));
  if (!existing.has(safe)) return safe;
  for (let i = 2; i < 100; i++) {
    const name = `${safe}_${i}`.slice(0, 99);
    if (!existing.has(name)) return name;
  }
  return `${safe}_${new Date().getTime()}`.slice(0, 99);
}

function _getProductImageUrl(asin) {
  if (!asin) return null;

  const config = getEnvConfig();
  const keepaApiEndpoint = 'https://api.keepa.com/product';
  const amazonImageBaseUrl = 'https://images-na.ssl-images-amazon.com/images/I/';
  const url = `${keepaApiEndpoint}?key=${config.KEEPA_API_KEY}&domain=5&asin=${asin}`;

  try {
    const response = UrlFetchApp.fetch(url, { method: 'get', muteHttpExceptions: true });
    const json = JSON.parse(response.getContentText());
    if (json.error || !json.products || json.products.length === 0) {
      return null;
    }

    const product = json.products[0];
    const imagesCSV = product.imagesCSV;
    if (!imagesCSV) return null;
    const firstImageFile = imagesCSV.split(',')[0];
    return `${amazonImageBaseUrl}${firstImageFile}._SL100_.jpg`;
  } catch (e) {
    console.warn(`[検品] Keepa画像取得に失敗: ASIN=${asin}, error=${e.message}`);
    return null;
  }
}


