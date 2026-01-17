function createInboundPlanForRows(sheet, accessToken) {
  const aggregatedItems = sheet.aggregateItems();
  const items = Object.values(aggregatedItems);

  if (items.length === 0) {
    throw new Error('納品プランを作成できる有効なSKUがありません');
  }

  const planCreator = new InboundPlanCreator(accessToken);
  const planResult = planCreator.createPlan(items);

  sheet.writePlanResult(planResult);
  _recordInboundPlanToWorkRecord_(planResult, items);
  return planResult;
}

function createInboundPlanFromActiveRows() {
  const config = getEnvConfig();
  const accessToken = getAuthToken();

  const sheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  sheet.getActiveRowData();
  const result = createInboundPlanForRows(sheet, accessToken);
  console.log(`Inbound plan created: inboundPlanId=${result.inboundPlanId}, link=${result.link}`);
  return result;
}

function _recordInboundPlanToWorkRecord_(planResult, items) {
  const config = getEnvConfig();
  const sheetName = config.WORK_RECORD_SHEET_NAME;
  if (!sheetName) return;

  // ASINごとに数量を集計（itemsは SKU でまとまっているが、ASINは同一想定）
  const qtyByAsin = new Map();
  for (const item of (items || [])) {
    const asin = String((item && item.asin) || '').trim();
    const qty = Number((item && item.quantity) || 0);
    if (!asin || !qty || qty <= 0) continue;
    qtyByAsin.set(asin, (qtyByAsin.get(asin) || 0) + qty);
  }

  const asinQuantities = Array.from(qtyByAsin.entries()).map(([asin, quantity]) => ({ asin, quantity }));
  if (asinQuantities.length === 0) return;

  const workRecord = new WorkRecordSheet(sheetName);
  workRecord.appendInboundPlanSummary(planResult, asinQuantities);
  console.log(`[作業記録] 納品プラン記録: rows=${asinQuantities.length}, inboundPlanId=${planResult && planResult.inboundPlanId ? planResult.inboundPlanId : ''}`);
}
