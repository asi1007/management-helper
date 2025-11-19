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

// getColumnIndicesはSettingSheetクラスのメソッドに統合されました

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

function aggregateItemsBySku(data, skuIndex, quantityIndex, labelOwnerIndices, prepOwnerIndices, labelOwnerFallback, prepOwnerFallback) {
  const aggregatedItems = {};
  
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    const sku = row[skuIndex];
    const quantity = Number(row[quantityIndex]);
    
    if (!sku || !quantity || quantity <= 0) {
      console.warn(`納品プラン対象外: sku=${sku}, quantity=${quantity}`);
      continue;
    }
    
    const labelOwner = pickOwnerValue(row, labelOwnerIndices, labelOwnerFallback, 'SELLER');
    const prepOwner = pickOwnerValue(row, prepOwnerIndices, prepOwnerFallback, 'SELLER');
    
    if (!aggregatedItems[sku]) {
      aggregatedItems[sku] = {
        msku: sku,
        quantity: 0,
        labelOwner: labelOwner,
        prepOwner: prepOwner
      };
    } else {
      aggregatedItems[sku].labelOwner = updateOwner(
        aggregatedItems[sku].labelOwner,
        labelOwner,
        labelOwnerFallback,
        sku,
        'labelOwner'
      );
      aggregatedItems[sku].prepOwner = updateOwner(
        aggregatedItems[sku].prepOwner,
        prepOwner,
        prepOwnerFallback,
        sku,
        'prepOwner'
      );
    }
    aggregatedItems[sku].quantity += quantity;
  }
  
  return aggregatedItems;
}

function writePlanLinksToRows(sheet, data, skuIndex, planColumnIndex, link) {
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    const sku = row[skuIndex];
    const rowNum = sheet.rowNumbers[i];
    if (!sku || !rowNum) {
      continue;
    }
    sheet.writePlanLink(link, rowNum, planColumnIndex);
  }
}

function createInboundPlanForRows(sheet, setting, data, accessToken) {
  // 必須設定を一度に取得
  const { "納品プラン": planColumnIndex, "sku": skuIndex, "数量": quantityIndex } = setting.getMultiple(["納品プラン", "sku", "数量"]);
  
  // オプション設定を一度に取得
  const labelOwnerIndices = setting.getColumnIndices(["labelOwner", "ラベル担当"]);
  const prepOwnerIndices = setting.getColumnIndices(["prepOwner", "梱包者"]);

  const labelOwnerFallback = 'SELLER';
  const prepOwnerFallback = prepOwnerIndices.length > 0 ? 'NONE' : 'SELLER';
  
  // SKUごとにアイテムを集約
  const aggregatedItems = aggregateItemsBySku(
    data,
    skuIndex,
    quantityIndex,
    labelOwnerIndices,
    prepOwnerIndices,
    labelOwnerFallback,
    prepOwnerFallback
  );

  const items = Object.values(aggregatedItems);
  if (items.length === 0) {
    throw new Error('納品プランを作成できる有効なSKUがありません');
  }

  // プランを作成
  const planCreator = new InboundPlanCreator(accessToken);
  const planResult = planCreator.createPlan(items);

  // プランリンクを各選択行に書き込み
  writePlanLinksToRows(sheet, data, skuIndex, planColumnIndex, planResult.link);

  // 発送日を書き込み
  try {
    sheet.writeDate("発送日", new Date());
  } catch (e) {
    console.warn(`発送日列への書き込みに失敗しました: ${e.message}`);
  }

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

