function loadLabelPDF(labelItems, accessToken) {
  const skuDownloader = new Downloader(accessToken);
  const now = new Date();
  const datetimeStr = Utilities.formatDate(now, 'JST', 'yyyy-MM-dd');
  const skuNums = (labelItems || []).map(i => i.toMskuQuantity());
  const result = skuDownloader.downloadLabels(skuNums, datetimeStr);
  return result.url;
}

function createInspectionSheetAndWriteLink(sheet, data) {
  // 検品シート（詳細検品マスタにASINがある場合のみ）
  try {
    const inspectionUrl = createInspectionSheetFromPurchaseRowsIfNeeded(data);
    if (inspectionUrl) {
      console.log(`検品シートを作成しました: ${inspectionUrl}`);
      // 仕入管理シート C2 に検品シートURLを記載
      sheet.writeCell(2, 3, { type: 'formula', value: `=HYPERLINK("${inspectionUrl}", "検品シート")` });
    }
    return inspectionUrl || null;
  } catch (e) {
    console.warn(`検品シート作成でエラー: ${e.message}`);
    return null;
  }
}

function createLabelPDF(data, accessToken) {
  const aggregator = new LabelAggregator();
  const items = aggregator.aggregate(data); // itemsが空ならaggregate内で例外
  const labelURL = loadLabelPDF(items, accessToken);
  return labelURL;
}

function createInstructionSheet(data) {
  return new InstructionSheet().create(data);
}


function generateLabelsAndInstructions() {
  const config = getEnvConfig();
  const accessToken = getAuthToken();
  const sheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  const data = sheet.getActiveRowData();
  // 指示書作成前にSKU空白を補完（ASIN -> SKU）
  sheet.fillMissingSkusFromAsins(accessToken, data);
  // FNSKUも補完（SKU -> FNSKU）
  sheet.fetchMissingFnskus(accessToken);
  
  try {
    createInspectionSheetAndWriteLink(sheet, data);
    const labelURL = createLabelPDF(data, accessToken);
    const instructionURL = createInstructionSheet(data);
    
    writeToSheet(sheet, data, instructionURL, labelURL);

  } catch (error) {
    console.error(`Error generating label or instruction:`, error.message);
    console.error(`Stack trace:`, error.stack);
    throw error;
  }
}


function writeToSheet(sheet, data, instructionURL, labelURL) {
  const dateOnly = new Date();
  dateOnly.setHours(0, 0, 0, 0);
  sheet.writeColumn("梱包依頼日", dateOnly);

  // プラン別名列に日付と納品分類を書き込む（指示書URLへのリンクとして）
  try {
    sheet.writePlanNameToRows(instructionURL);
  } catch (error) {
    console.warn(`プラン別名列への書き込みでエラーが発生しました: ${error.message}`);
  }

  sheet.writeCell(2, 1, { type: 'formula', value: `=HYPERLINK("${labelURL}", "ラベルデータ")` });
  sheet.writeCell(2, 2, { type: 'formula', value: `=HYPERLINK("${instructionURL}", "指示書")` });
}

