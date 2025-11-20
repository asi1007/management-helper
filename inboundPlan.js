function normalizeOwner(value, fallback, defaultIfUnknown = 'SELLER') {
  if (value === undefined || value === null || value === '') {
    return fallback;
  }
  
  const trimmed = String(value).trim();
  const upper = trimmed.toUpperCase();
  
  const mapping = {
    'アマゾン': 'AMAZON',
    'AMZN': 'AMAZON',
    'AMAZON': 'AMAZON',
    'セラー': 'SELLER',
    '出品者': 'SELLER',
    'SELLER': 'SELLER',
    '自社': 'SELLER',
    'なし': 'NONE',
    '無し': 'NONE',
    '不要': 'NONE',
    'NONE': 'NONE'
  };
  
  const allowedOwners = ['AMAZON', 'SELLER', 'NONE'];
  let normalized = mapping[upper] || mapping[trimmed] || upper;
  
  if (allowedOwners.indexOf(normalized) >= 0) {
    return normalized;
  }
  
  if (normalized.indexOf('SELLER') >= 0 || trimmed.indexOf('出品') >= 0 || trimmed.indexOf('自社') >= 0) {
    return 'SELLER';
  }
  
  if (normalized.indexOf('AMAZON') >= 0 || trimmed.indexOf('アマゾン') >= 0 || trimmed.indexOf('ＡＭＡＺＯＮ') >= 0) {
    return 'AMAZON';
  }
  
  console.warn(`不明なオーナー指定 "${value}" を検出しました。fallback=${fallback} を適用します。`);
  if (fallback === 'NONE') {
    return defaultIfUnknown;
  }
  return fallback;
}

function pickOwnerValue(row, indices, fallback, defaultIfUnknown) {
  for (const idx of indices) {
    if (idx !== null && idx !== undefined) {
      const candidate = row[idx];
      if (candidate !== undefined && candidate !== null && String(candidate).trim() !== '') {
        return normalizeOwner(candidate, fallback, defaultIfUnknown);
      }
    }
  }
  return fallback;
}

function updateOwner(current, incoming, fallback, sku, label) {
  if (current === incoming) {
    return current;
  }
  if (current === fallback && incoming !== fallback) {
    return incoming;
  }
  if (incoming === fallback) {
    return current;
  }
  console.warn(`SKU ${sku} の${label}が複数行で異なります: current=${current}, incoming=${incoming}。最初の値を使用します。`);
  return current;
}

function enrichRowsWithOwners(data, skuIndex, labelOwnerIndices, prepOwnerIndices, labelOwnerFallback, prepOwnerFallback) {
  const enrichedRows = data.map(row => {
    const sku = row[skuIndex];
    const labelOwner = pickOwnerValue(row, labelOwnerIndices, labelOwnerFallback, 'SELLER');
    const prepOwner = pickOwnerValue(row, prepOwnerIndices, prepOwnerFallback, 'SELLER');
    return {
      row: row,
      sku: sku,
      labelOwner: labelOwner,
      prepOwner: prepOwner
    };
  });

  const skuOwners = {};
  for (const item of enrichedRows) {
    const sku = item.sku;
    if (!sku) continue;
    
    if (!skuOwners[sku]) {
      skuOwners[sku] = {
        labelOwner: item.labelOwner,
        prepOwner: item.prepOwner
      };
    } else {
      skuOwners[sku].labelOwner = updateOwner(
        skuOwners[sku].labelOwner,
        item.labelOwner,
        labelOwnerFallback,
        sku,
        'labelOwner'
      );
      skuOwners[sku].prepOwner = updateOwner(
        skuOwners[sku].prepOwner,
        item.prepOwner,
        prepOwnerFallback,
        sku,
        'prepOwner'
      );
    }
  }

  return enrichedRows.map(item => ({
    ...item,
    labelOwner: skuOwners[item.sku]?.labelOwner || item.labelOwner,
    prepOwner: skuOwners[item.sku]?.prepOwner || item.prepOwner
  }));
}

function aggregateItemsBySku(enrichedData, skuIndex, quantityIndex) {
  const aggregatedItems = {};
  
  for (let i = 0; i < enrichedData.length; i++) {
    const item = enrichedData[i];
    const sku = item.sku;
    const quantity = Number(item.row[quantityIndex]);
    
    if (!sku || !quantity || quantity <= 0) {
      console.warn(`納品プラン対象外: sku=${sku}, quantity=${quantity}`);
      continue;
    }
    
    if (!aggregatedItems[sku]) {
      aggregatedItems[sku] = {
        msku: sku,
        quantity: 0,
        labelOwner: item.labelOwner,
        prepOwner: item.prepOwner
      };
    }
    aggregatedItems[sku].quantity += quantity;
  }
  
  return aggregatedItems;
}


function createInboundPlanForRows(sheet, setting, data, accessToken) {
  // 必須設定を一度に取得
  const { "sku": skuIndex, "数量": quantityIndex } = setting.getMultiple(["sku", "数量"]);
  
  // オプション設定を一度に取得
  const labelOwnerIndices = setting.getColumnIndices(["labelOwner", "ラベル担当"]);
  const prepOwnerIndices = setting.getColumnIndices(["prepOwner", "梱包者"]);

  const labelOwnerFallback = 'SELLER';
  const prepOwnerFallback = prepOwnerIndices.length > 0 ? 'NONE' : 'SELLER';
  
  // 各行にlabelOwnerとprepOwnerを追加し、同じSKUのオーナー値を統合
  const enrichedData = enrichRowsWithOwners(data, skuIndex, labelOwnerIndices, prepOwnerIndices, labelOwnerFallback, prepOwnerFallback);
  
  // SKUごとにアイテムを集約
  const aggregatedItems = aggregateItemsBySku(enrichedData, skuIndex, quantityIndex);

  const items = Object.values(aggregatedItems);
  if (items.length === 0) {
    throw new Error('納品プランを作成できる有効なSKUがありません');
  }

  // プランを作成
  const planCreator = new InboundPlanCreator(accessToken);
  const planResult = planCreator.createPlan(items);

  // プランリンクと発送日を書き込み
  if (planResult.link) {
    const planColumnIndex = setting.get("納品プラン");
    const linkFormula = `=HYPERLINK("${planResult.link}", "納品プラン")`;
    sheet.writeColumn("納品プラン", { type: 'formula', value: linkFormula });
  }
  
  const dateOnly = new Date();
  dateOnly.setHours(0, 0, 0, 0);
  sheet.writeColumn("発送日", dateOnly);

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

