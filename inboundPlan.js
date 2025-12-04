function aggregateItems(data, skuIndex, quantityIndex) {
  const aggregatedItems = {};
  const labelOwner = 'SELLER';
  
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    const sku = row[skuIndex];
    const quantity = Number(row[quantityIndex]);
    
    if (!sku || !quantity || quantity <= 0) {
      console.warn(`納品プラン対象外: sku=${sku}, quantity=${quantity}`);
      continue;
    }
    
    if (!aggregatedItems[sku]) {
      aggregatedItems[sku] = {
        msku: sku,
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
    const planNameText = generatePlanNameText(data, setting);
    const linkFormula = `=HYPERLINK("${planResult.link}", "${planNameText}")`;
    sheet.writeColumn("納品プラン", { type: 'formula', value: linkFormula });
  }
  
  const dateOnly = new Date();
  dateOnly.setHours(0, 0, 0, 0);
  sheet.writeColumn("発送日", dateOnly);
}

function handlePrepOwnerError(error, itemMap, regex, newOwnerValue, logMessage) {
  const match = error.message.match(regex);
  if (match) {
    const msku = match[1];
    const item = itemMap.get(msku);
    if (item) {
      console.log(logMessage.replace('${msku}', msku));
      item.prepOwner = newOwnerValue;
      return true;
    }
  }
  return false;
}

function initializeItemsWithPrepOwner(items) {
  return items.map(item => ({
    ...item,
    prepOwner: 'NONE'
  }));
}

function parseErrorsFromMessage(errorMessage) {
  const jsonMatch = errorMessage.match(/\[.*\]/);
  if (!jsonMatch) {
    return null;
  }
  
  try {
    return JSON.parse(jsonMatch[0]);
  } catch (jsonError) {
    return null;
  }
}

function handlePrepOwnerErrors(errors, itemMap) {
  let needsRetry = false;
  
  for (const error of errors) {
    const requiresPrepOwner = handlePrepOwnerError(
      error, 
      itemMap, 
      /ERROR: (.+?) requires prepOwner/, 
      'SELLER', 
      'SKU ${msku} は梱包が必要なため、prepOwnerをSELLERに変更します。'
    );
    
    const doesNotRequirePrepOwner = handlePrepOwnerError(
      error, 
      itemMap, 
      /ERROR: (.+?) does not require prepOwner/, 
      'NONE', 
      'SKU ${msku} は梱包不要なため、prepOwnerをNONEに変更します。'
    );
    
    needsRetry = needsRetry || requiresPrepOwner || doesNotRequirePrepOwner;
  }
  
  return needsRetry;
}

function createInboundPlanWithRetry(planCreator, items, maxRetries) {
  let currentItems = items;
  let retryCount = 0;

  while (true) {
    try {
      return planCreator.createPlan(currentItems);
    } catch (e) {
      if (retryCount >= maxRetries) {
        console.error(`最大リトライ回数(${maxRetries})を超えました。最後のエラー: ${e.message}`);
        throw e;
      }

      const errors = parseErrorsFromMessage(e.message);
      if (!errors) {
        console.error(`prepOwner以外のエラーが発生しました: ${e.message}`);
        throw e;
      }

      const itemMap = new Map(currentItems.map(item => [item.msku, item]));
      const needsRetry = handlePrepOwnerErrors(errors, itemMap);

      if (!needsRetry) {
        console.error(`prepOwner以外のエラーが発生しました: ${e.message}`);
        throw e;
      }
      
      console.log(`prepOwner設定を修正して再試行します (${retryCount + 1}/${maxRetries})`);
      retryCount++;
    }
  }
}

function createInboundPlanForRows(sheet, setting, data, accessToken) {
  const { "sku": skuIndex, "数量": quantityIndex } = setting.getMultiple(["sku", "数量"]);
  const aggregatedItems = aggregateItems(data, skuIndex, quantityIndex);
  const items = Object.values(aggregatedItems);
  
  if (items.length === 0) {
    throw new Error('納品プランを作成できる有効なSKUがありません');
  }

  const initializedItems = initializeItemsWithPrepOwner(items);
  const planCreator = new InboundPlanCreator(accessToken);
  const planResult = createInboundPlanWithRetry(planCreator, initializedItems, 3);
  
  writePlanResultToSheet(sheet, setting, planResult, data);
  return planResult;
}

function createInboundPlanFromActiveRows() {
  const { config, setting, accessToken } = getConfigSettingAndToken();

  const sheet = new Sheet(config.SHEET_ID, config.PURCHASE_SHEET_NAME, setting);
  const data = sheet.getActiveRowData();

  const result = createInboundPlanForRows(sheet, setting, data, accessToken);
  console.log(`Inbound plan created: inboundPlanId=${result.inboundPlanId}, operationId=${result.operationId}, link=${result.link}`);
  return result;
}

