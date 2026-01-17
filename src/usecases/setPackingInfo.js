/* exported setPackingInfoFromActiveRow, submitPackingInfoFromDialog */

function _parseCartonInput(inputText) {
  const entries = String(inputText || '')
    .split(/\s+(?=\d+(?:-\d+)?[：:])/)
    .map(s => s.trim())
    .filter(Boolean);

  const cartons = [];

  for (const entry of entries) {
    const match1 = entry.match(/^(\d+(?:-\d+)?)\s*[：:]\s*(\d+(?:\.\d+)?)\s*[*×x]\s*(\d+(?:\.\d+)?)\s*[*×x]\s*(\d+(?:\.\d+)?)\s*(?:cm)?\s+(\d+(?:\.\d+)?)\s*(?:KG|kg)?$/i);
    const match2 = entry.match(/^(\d+(?:-\d+)?)\s*[：:]\s*(\d+(?:\.\d+)?)\s*(?:KG|kg)?\s+(\d+(?:\.\d+)?)\s*[*×x]\s*(\d+(?:\.\d+)?)\s*[*×x]\s*(\d+(?:\.\d+)?)\s*(?:cm)?$/i);

    let boxRange, lengthCm, widthCm, heightCm, weightKg;

    if (match1) {
      [, boxRange, lengthCm, widthCm, heightCm, weightKg] = match1;
    } else if (match2) {
      [, boxRange, weightKg, lengthCm, widthCm, heightCm] = match2;
    } else {
      throw new Error(`解析できない: "${entry}"\n形式1: 箱番号：長さ*幅*高さ 重さKG\n形式2: 箱番号：重さKG 長さ*幅*高さcm`);
    }

    const dimensions = {
      length: parseFloat(lengthCm),
      width: parseFloat(widthCm),
      height: parseFloat(heightCm)
    };
    const weight = parseFloat(weightKg);

    if (boxRange.includes('-')) {
      const [start, end] = boxRange.split('-').map(Number);
      for (let i = start; i <= end; i++) {
        cartons.push({ boxNumber: i, dimensions, weight });
      }
    } else {
      cartons.push({ boxNumber: parseInt(boxRange, 10), dimensions, weight });
    }
  }

  cartons.sort((a, b) => a.boxNumber - b.boxNumber);
  return cartons;
}

function _cmToInches(cm) {
  return Math.round(cm / 2.54 * 100) / 100;
}

function _kgToLbs(kg) {
  return Math.round(kg * 2.20462 * 100) / 100;
}

function _extractInboundPlanIdFromCell(cellValue) {
  const value = String(cellValue || '');
  const wfMatch = value.match(/wf[a-f0-9-]+/i);
  if (wfMatch) {
    return wfMatch[0];
  }
  if (/^wf[a-f0-9-]+$/i.test(value.trim())) {
    return value.trim();
  }
  throw new Error(`納品プランIDを特定できません: "${value}"`);
}

function setPackingInfoFromActiveRow() {
  const config = getEnvConfig();
  const sheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  sheet.getActiveRowData();

  if (sheet.data.length === 0) {
    throw new Error('選択された行がありません');
  }

  const row = sheet.data[0];
  const planCellValue = row.get('納品プラン');
  const inboundPlanId = _extractInboundPlanIdFromCell(planCellValue);

  console.log(`[setPackingInfo] inboundPlanId=${inboundPlanId}`);

  _showPackingInfoDialog_(inboundPlanId);
}

function _showPackingInfoDialog_(inboundPlanId) {
  const ui = SpreadsheetApp.getUi();
  const response = ui.prompt(
    '荷物情報入力',
    `InboundPlanId: ${inboundPlanId}\n\n荷物情報を入力してください（1行に1パターン）:\n形式: 箱番号：長さ*幅*高さ 重さKG\n例: 1-2：60*40*32 29.1KG`,
    ui.ButtonSet.OK_CANCEL
  );

  if (response.getSelectedButton() !== ui.Button.OK) {
    console.log('[setPackingInfo] キャンセルされました');
    return;
  }

  const cartonInputText = response.getResponseText();
  if (!cartonInputText || !cartonInputText.trim()) {
    throw new Error('荷物情報が入力されていません');
  }

  const result = submitPackingInfoFromDialog(inboundPlanId, cartonInputText);
  ui.alert('完了', `荷物情報を送信しました\nboxCount: ${result.boxCount}`, ui.ButtonSet.OK);
}

function submitPackingInfoFromDialog(inboundPlanId, cartonInputText) {
  console.log(`[submitPackingInfoFromDialog] start: inboundPlanId=${inboundPlanId}`);

  let accessToken;
  try {
    accessToken = getAuthToken();
    console.log(`[submitPackingInfoFromDialog] accessToken取得成功`);
  } catch (e) {
    console.error(`[submitPackingInfoFromDialog] accessToken取得失敗: ${e.message}`);
    throw e;
  }

  const creator = new InboundPlanCreator(accessToken);

  const cartons = _parseCartonInput(cartonInputText);
  console.log(`[setPackingInfo] parsed cartons: ${JSON.stringify(cartons)}`);

  const packingGroupId = creator.getPackingGroupId(inboundPlanId);
  console.log(`[setPackingInfo] packingGroupId=${packingGroupId}`);

  const items = creator.getPackingGroupItems(inboundPlanId, packingGroupId);
  console.log(`[setPackingInfo] items count=${items.length}`);

  const result = creator.setPackingInformation(inboundPlanId, packingGroupId, cartons, items);
  console.log(`[setPackingInfo] result: ${JSON.stringify(result)}`);

  return result;
}

function testSubmitPackingInfo() {
  const result = submitPackingInfoFromDialog('wf5db5a649-f80b-412c-bdad-816c8d6d540e', '1：60*40*32 29.1KG');
  console.log(result);
}

function debugPlacementOptions() {
  const accessToken = getAuthToken();

  // 最新のinboundPlanIdを入力してください
  const inboundPlanId = 'wff38cf348-23c2-42a6-a4e5-52f962d2df17';

  const baseUrl = 'https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20';
  const headers = {
    'Accept': 'application/json',
    'x-amz-access-token': accessToken
  };

  // 1. Shipments一覧を取得
  console.log('=== Shipments ===');
  const shipmentsRes = UrlFetchApp.fetch(`${baseUrl}/inboundPlans/${inboundPlanId}/shipments`, {
    method: 'get', muteHttpExceptions: true, headers
  });
  const shipmentsJson = JSON.parse(shipmentsRes.getContentText());
  console.log(JSON.stringify(shipmentsJson, null, 2));

  // 2. 各Shipmentの詳細を取得
  const shipments = shipmentsJson.shipments || [];
  for (const s of shipments) {
    const shipmentId = s.shipmentId;
    console.log(`\n=== Shipment Detail: ${shipmentId} ===`);

    // Shipment詳細
    try {
      const detailRes = UrlFetchApp.fetch(`${baseUrl}/inboundPlans/${inboundPlanId}/shipments/${shipmentId}`, {
        method: 'get', muteHttpExceptions: true, headers
      });
      console.log('Shipment:', detailRes.getContentText());
    } catch (e) {
      console.log('Shipment detail error:', e.message);
    }

    // Transportation Options（配送オプション）
    console.log(`\n=== Transportation Options for ${shipmentId} ===`);
    try {
      const transRes = UrlFetchApp.fetch(`${baseUrl}/inboundPlans/${inboundPlanId}/shipments/${shipmentId}/transportationOptions`, {
        method: 'get', muteHttpExceptions: true, headers
      });
      console.log('Transportation Options:', transRes.getContentText());
    } catch (e) {
      console.log('Transportation Options error:', e.message);
    }

    // Delivery Window Options
    console.log(`\n=== Delivery Window Options for ${shipmentId} ===`);
    try {
      const dwRes = UrlFetchApp.fetch(`${baseUrl}/inboundPlans/${inboundPlanId}/shipments/${shipmentId}/deliveryWindowOptions`, {
        method: 'get', muteHttpExceptions: true, headers
      });
      console.log('Delivery Window Options:', dwRes.getContentText());
    } catch (e) {
      console.log('Delivery Window Options error:', e.message);
    }
  }

  // 3. PackingGroups
  console.log('\n=== Packing Groups ===');
  try {
    const pgRes = UrlFetchApp.fetch(`${baseUrl}/inboundPlans/${inboundPlanId}/packingGroups`, {
      method: 'get', muteHttpExceptions: true, headers
    });
    console.log('Packing Groups:', pgRes.getContentText());
  } catch (e) {
    console.log('Packing Groups error:', e.message);
  }
}
