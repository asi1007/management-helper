// 定数

function makeInstructionSheet(data) {
  const instructionSheet = new InstructionSheet();
  return instructionSheet.create(data);
}

function loadLabelPDF(skuNums, accessToken) {
  const skuDownloader = new Downloader(accessToken);
  const now = new Date();
  const datetimeStr = Utilities.formatDate(now, 'JST', 'yyyy-MM-dd');
  const result = skuDownloader.downloadLabels(skuNums, datetimeStr);
  return result.url;
}

function formatDateMMDD(date) {
  const month = String(date.getMonth() + 1);
  const day = String(date.getDate());
  const monthStr = month.length === 1 ? '0' + month : month;
  const dayStr = day.length === 1 ? '0' + day : day;
  return `${monthStr}/${dayStr}`;
}

function fetchMissingFnskus(sheet, data, accessToken) {
  const fnskuGetter = new FnskuGetter(accessToken);
  
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    let fnsku = '';
    let msku = '';
    try { fnsku = row.get("FNSKU") || ''; } catch (e) {}
    try { msku = row.get("sku") || ''; } catch (e) {}
    const rowNum = row.rowNumber;
    
    if (!fnsku || fnsku === '') {
      console.log(`FNSKU is empty for ${msku}, fetching...`);
      // getFnskuは必ずfnSkuを返すか、エラーをスローする
      const fetchedFnsku = fnskuGetter.getFnsku(msku);
      
        console.log(`Fetched FNSKU for ${msku}: ${fetchedFnsku}`);
      const col = sheet._getColumnIndexByName("FNSKU") + 1;
      if (rowNum && col >= 1) {
          sheet.sheet.getRange(rowNum, col).setValue(fetchedFnsku);
        // BaseRow(Array)互換なのでインデックス更新もできるが、get()参照のためここでは不要
      }
    }
  }
}

function aggregateSkusForLabels(data) {
  const skuNums = data.map(row => ({
    msku: row.get("sku"),
    quantity: row.get("数量")
  }));
  
  // 空のSKUをフィルタリング
  const validSkuNums = skuNums.filter(s => s.msku && s.msku !== '' && s.quantity && s.quantity > 0);
  
  if (validSkuNums.length === 0) {
    throw new Error('有効なSKUがありません');
  }
  
  // 同じSKUの数量を合算
  const aggregatedSkuNums = {};
  for (const item of validSkuNums) {
    const msku = item.msku;
    const quantity = Number(item.quantity) || 0;
    aggregatedSkuNums[msku] = (aggregatedSkuNums[msku] || 0) + quantity;
  }
  
  // オブジェクトを配列に変換
  return Object.keys(aggregatedSkuNums).map(msku => ({
    msku: msku,
    quantity: aggregatedSkuNums[msku]
  }));
}

function writePlanNameToRows(sheet, data, instructionURL) {
  let planNameColumn = null;
  let deliveryCategoryColumn = null;
  try { planNameColumn = sheet._getColumnIndexByName("プラン別名"); } catch (e) { planNameColumn = null; }
  try { deliveryCategoryColumn = sheet._getColumnIndexByName("納品分類"); } catch (e) { deliveryCategoryColumn = null; }
  const dateStr = formatDateMMDD(new Date());
  
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    const rowNum = row.rowNumber;
    const deliveryCategory = deliveryCategoryColumn !== null ? (row[deliveryCategoryColumn] || '') : '';
    const planNameValue = `${dateStr}${deliveryCategory}`;
    
    if (planNameColumn !== null) {
      const col = planNameColumn + 1;
      if (rowNum && col >= 1 && instructionURL) {
        const linkFormula = `=HYPERLINK("${instructionURL}", "${planNameValue}")`;
        sheet.sheet.getRange(rowNum, col).setFormula(linkFormula);
      } else if (rowNum && col >= 1) {
        sheet.sheet.getRange(rowNum, col).setValue(planNameValue);
      }
    }
  }
}

function generateLabelsAndInstructions() {
  const config = getEnvConfig();
  const accessToken = getAuthToken();
  const sheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  const data = sheet.getActiveRowData();

  // FNSKUが空白の場合はSP-APIから取得
  fetchMissingFnskus(sheet, data, accessToken);
  
  try {
    // 検品シート（詳細検品マスタにASINがある場合のみ）
    try {
      const inspectionUrl = createInspectionSheetFromPurchaseRowsIfNeeded(data);
      if (inspectionUrl) {
        console.log(`検品シートを作成しました: ${inspectionUrl}`);
      }
    } catch (e) {
      console.warn(`検品シート作成でエラー: ${e.message}`);
    }

    // ラベルPDFを生成
    const finalSkuNums = aggregateSkusForLabels(data);
    const labelURL = loadLabelPDF(finalSkuNums, accessToken);
    const instructionURL = makeInstructionSheet(data);
    writeToSheet(sheet, data, instructionURL, labelURL);

  } catch (error) {
    console.error(`Error generating label or instruction:`, error.message);
    console.error(`Stack trace:`, error.stack);
    throw error;
  }
}


function writeToSheet(sheet, data, instructionURL, labelURL) {
  // 依頼日列に本日日付（時刻は00:00:00）を書き込む
  const dateOnly = new Date();
  dateOnly.setHours(0, 0, 0, 0);
  sheet.writeColumn("依頼日", dateOnly);

  // プラン別名列に日付と納品分類を書き込む（指示書URLへのリンクとして）
  try {
    writePlanNameToRows(sheet, data, instructionURL);
  } catch (error) {
    console.warn(`プラン別名列への書き込みでエラーが発生しました: ${error.message}`);
  }

  sheet.writeCell(2, 1, { type: 'formula', value: `=HYPERLINK("${labelURL}", "ラベルデータ")` });
  sheet.writeCell(2, 2, { type: 'formula', value: `=HYPERLINK("${instructionURL}", "指示書")` });
}

