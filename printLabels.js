// 定数

function makeOrderInstructionSheet(data, setting) {
  const instructionSheet = new OrderInstructionSheet(setting);
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

function fetchMissingFnskus(sheet, data, fnskuColumn, skuColumn, accessToken) {
  const fnskuGetter = new FnskuGetter(accessToken);
  
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    const fnsku = row[fnskuColumn];
    const msku = row[skuColumn];
    const rowNum = sheet.rowNumbers[i];
    
    if (!fnsku || fnsku === '') {
      console.log(`FNSKU is empty for ${msku}, fetching...`);
      // getFnskuは必ずfnSkuを返すか、エラーをスローする
      const fetchedFnsku = fnskuGetter.getFnsku(msku);
      
        console.log(`Fetched FNSKU for ${msku}: ${fetchedFnsku}`);
        const col = fnskuColumn + 1;
      if (rowNum && col >= 1) {
          sheet.sheet.getRange(rowNum, col).setValue(fetchedFnsku);
        row[fnskuColumn] = fetchedFnsku; // データ配列も更新
      }
    }
  }
}

function aggregateSkusForLabels(data, setting) {
  const skuNums = data.map(row => ({
    msku: row[setting.get("sku")],
    quantity: row[setting.get("数量")]
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

function writePlanNameToRows(sheet, data, setting, instructionURL) {
  const planNameColumn = setting.getOptional ? setting.getOptional("プラン別名") : null;
  const deliveryCategoryColumn = setting.getOptional ? setting.getOptional("納品分類") : null;
  const dateStr = formatDateMMDD(new Date());
  
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    const rowNum = sheet.rowNumbers[i];
    const deliveryCategory = row[deliveryCategoryColumn] || '';
    const planNameValue = `${dateStr}${deliveryCategory}`;
    
    const col = planNameColumn + 1;
    if (rowNum && col >= 1 && instructionURL) {
      const linkFormula = `=HYPERLINK("${instructionURL}", "${planNameValue}")`;
      sheet.sheet.getRange(rowNum, col).setFormula(linkFormula);
    } else if (rowNum && col >= 1) {
      sheet.sheet.getRange(rowNum, col).setValue(planNameValue);
    }
  }
}

function generateLabelsAndInstructions() {
  const { config, setting, accessToken } = getConfigSettingAndToken();
  const sheet = new Sheet(config.SHEET_ID, config.PURCHASE_SHEET_NAME, setting);
  const data = sheet.getActiveRowData();

  // FNSKUが空白の場合はSP-APIから取得
  const fnskuColumn = setting.get("fnsku");
  const skuColumn = setting.get("sku");
  fetchMissingFnskus(sheet, data, fnskuColumn, skuColumn, accessToken);
  
  try {
    // ラベルPDFを生成
    const finalSkuNums = aggregateSkusForLabels(data, setting);
    const labelURL = loadLabelPDF(finalSkuNums, accessToken);
    const instructionURL = makeOrderInstructionSheet(data, setting);
    writeToSheet(sheet, data, setting, instructionURL, labelURL);

  } catch (error) {
    console.error(`Error generating label or instruction:`, error.message);
    console.error(`Stack trace:`, error.stack);
    throw error;
  }
}


function writeToSheet(sheet, data, setting, instructionURL, labelURL) {
  // 依頼日列に本日日付（時刻は00:00:00）を書き込む
  const dateOnly = new Date();
  dateOnly.setHours(0, 0, 0, 0);
  sheet.writeColumn("依頼日", dateOnly);

  // プラン別名列に日付と納品分類を書き込む（指示書URLへのリンクとして）
  try {
    writePlanNameToRows(sheet, data, setting, instructionURL);
  } catch (error) {
    console.warn(`プラン別名列への書き込みでエラーが発生しました: ${error.message}`);
  }

  sheet.writeCell(2, 1, { type: 'formula', value: `=HYPERLINK("${labelURL}", "ラベルデータ")` });
  sheet.writeCell(2, 2, { type: 'formula', value: `=HYPERLINK("${instructionURL}", "指示書")` });
}

