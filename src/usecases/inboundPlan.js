function createInboundPlanForRows(sheet, accessToken) {
  const aggregatedItems = sheet.aggregateItems();
  const items = Object.values(aggregatedItems);
  
  if (items.length === 0) {
    throw new Error('納品プランを作成できる有効なSKUがありません');
  }

  const planCreator = new InboundPlanCreator(accessToken);
  const planResult = planCreator.createPlan(items);
  
  sheet.writePlanResult(planResult);
  return planResult;
}

function createInboundPlanFromActiveRows() {
  const { config, setting, accessToken } = getConfigSettingAndToken();

  const sheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME, setting);
  sheet.getActiveRowData();
  const result = createInboundPlanForRows(sheet, accessToken);
  console.log(`Inbound plan created: inboundPlanId=${result.inboundPlanId}, operationId=${result.operationId}, link=${result.link}`);
  return result;
}

