function loadLabelPDF(labelItems, accessToken) {
  const skuDownloader = new Downloader(accessToken);
  const now = new Date();
  const datetimeStr = Utilities.formatDate(now, 'JST', 'yyyy-MM-dd');
  const skuNums = (labelItems || []).map(i => i.toMskuQuantity());
  const result = skuDownloader.downloadLabels(skuNums, datetimeStr);
  return result.url;
}


function generateLabelsAndInstructions() {
  const config = getEnvConfig();
  const accessToken = getAuthToken();
  const sheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  const data = sheet.getActiveRowData();
  sheet.fetchMissingFnskus(accessToken);
  
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
    const aggregator = new LabelAggregator();
    const items = aggregator.aggregate(data);
    const labelURL = loadLabelPDF(items, accessToken);

    const instructionURL = new InstructionSheet().create(data);
    
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

