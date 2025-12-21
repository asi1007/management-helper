function aggregateItems(data, skuIndex, quantityIndex, asinIndex) {
  const aggregatedItems = {};
  const labelOwner = 'SELLER';
  
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    const sku = row[skuIndex];
    const quantity = Number(row[quantityIndex]);
    const asin = row[asinIndex];
    
    if (!sku || !quantity || quantity <= 0) {
      console.warn(`納品プラン対象外: sku=${sku}, quantity=${quantity}`);
      continue;
    }
    
    if (!aggregatedItems[sku]) {
      aggregatedItems[sku] = {
        msku: sku,
        asin: asin,
        quantity: 0,
        labelOwner: labelOwner
      };
    }
    aggregatedItems[sku].quantity += quantity;
  }
  
  return aggregatedItems;
}

function formatDateMMDD(date) {
  const month = String(date.getMonth() + 1);
  const day = String(date.getDate());
  const monthStr = month.length === 1 ? '0' + month : month;
  const dayStr = day.length === 1 ? '0' + day : day;
  return `${monthStr}/${dayStr}`;
}

function generatePlanNameText(data, setting) {
  const deliveryCategoryColumn = setting.getOptional ? setting.getOptional("納品分類") : null;
  const dateStr = formatDateMMDD(new Date());
  const deliveryCategory = data.length > 0 && deliveryCategoryColumn !== null 
    ? (data[0][deliveryCategoryColumn] || '') 
    : '';
  return `${dateStr}${deliveryCategory}`;
}

function writePlanResultToSheet(sheet, setting, planResult, data) {
  if (planResult.link) {
    const displayText = planResult.inboundPlanId || generatePlanNameText(data, setting);
    
    const linkFormula = `=HYPERLINK("${planResult.link}", "${displayText}")`;
    sheet.writeColumn("納品プラン", { type: 'formula', value: linkFormula });
  }
  
  const dateOnly = new Date();
  dateOnly.setHours(0, 0, 0, 0);
  sheet.writeColumn("発送日", dateOnly);
}

function createInboundPlanForRows(sheet, setting, data, accessToken) {
  const { "sku": skuIndex, "数量": quantityIndex, "asin": asinIndex } = setting.getMultiple(["sku", "数量", "asin"]);
  const aggregatedItems = aggregateItems(data, skuIndex, quantityIndex, asinIndex);
  const items = Object.values(aggregatedItems);
  
  if (items.length === 0) {
    throw new Error('納品プランを作成できる有効なSKUがありません');
  }

  const planCreator = new InboundPlanCreator(accessToken);
  const planResult = planCreator.createPlan(items);
  
  writePlanResultToSheet(sheet, setting, planResult, data);
  return planResult;
}

function createInboundPlanFromActiveRows() {
  const { config, setting, accessToken } = getConfigSettingAndToken();

  const sheet = new PurchaseSheet(config.SHEET_ID, config.PURCHASE_SHEET_NAME, setting);
  const data = sheet.getActiveRowData();

  const result = createInboundPlanForRows(sheet, setting, data, accessToken);
  console.log(`Inbound plan created: inboundPlanId=${result.inboundPlanId}, operationId=${result.operationId}, link=${result.link}`);
  return result;
}

