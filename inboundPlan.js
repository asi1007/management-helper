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

function createInboundPlanForRows(sheet, setting, data, accessToken) {
  // 必須設定を一度に取得
  const { "sku": skuIndex, "数量": quantityIndex } = setting.getMultiple(["sku", "数量"]);
  
  // SKUごとにアイテムを集約
  const aggregatedItems = aggregateItems(data, skuIndex, quantityIndex);

  const items = Object.values(aggregatedItems);
  if (items.length === 0) {
    throw new Error('納品プランを作成できる有効なSKUがありません');
  }

  // 初期値として全てのアイテムのprepOwnerを'NONE'に設定
  let currentItems = items.map(item => ({
    ...item,
    prepOwner: 'NONE'
  }));

  // プランを作成 (エラー時のリトライロジック付き)
  const planCreator = new InboundPlanCreator(accessToken);
  let planResult;
  let retryCount = 0;
  const MAX_RETRIES = 3;

  while (true) {
    try {
      planResult = planCreator.createPlan(currentItems);
      break; // 成功したらループを抜ける
    } catch (e) {
      if (retryCount >= MAX_RETRIES) {
        console.error(`最大リトライ回数(${MAX_RETRIES})を超えました。最後のエラー: ${e.message}`);
        throw e;
      }

      const errorMessage = e.message;
      const jsonMatch = errorMessage.match(/\[.*\]/);
      if (!jsonMatch) throw e; // JSONが含まれていないエラーはそのまま投げる

      let errors;
      try {
        errors = JSON.parse(jsonMatch[0]);
      } catch (jsonError) {
        throw e; // JSONパースエラーならそのまま投げる
      }

      let needsRetry = false;
      // SKUをキーにしたマップを作成（高速検索用）
      const itemMap = new Map(currentItems.map(item => [item.msku, item]));

      for (const error of errors) {
        // パターン1: requires prepOwner but NONE was assigned -> SELLERにする
        // エラー例: "ERROR: SKU requires prepOwner but NONE was assigned"
        const requireMatch = error.message.match(/ERROR: (.+?) requires prepOwner/);
        if (requireMatch) {
          const msku = requireMatch[1];
          const item = itemMap.get(msku);
          if (item) {
            console.log(`SKU ${msku} は梱包が必要なため、prepOwnerをSELLERに変更します。`);
            item.prepOwner = 'SELLER';
            needsRetry = true;
          }
        }

        // パターン2: does not require prepOwner but SELLER was assigned -> NONEにする
        // エラー例: "ERROR: SKU does not require prepOwner but SELLER was assigned"
        const notRequireMatch = error.message.match(/ERROR: (.+?) does not require prepOwner/);
        if (notRequireMatch) {
          const msku = notRequireMatch[1];
          const item = itemMap.get(msku);
          if (item) {
            console.log(`SKU ${msku} は梱包不要なため、prepOwnerをNONEに変更します。`);
            item.prepOwner = 'NONE';
            needsRetry = true;
          }
        }
      }

      if (!needsRetry) {
        console.error(`prepOwner以外のエラーが発生しました: ${e.message}`);
        throw e; // prepOwner関連のエラーでなければそのまま投げる
      }
      
      console.log(`prepOwner設定を修正して再試行します (${retryCount + 1}/${MAX_RETRIES})`);
      retryCount++;
    }
  }

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

