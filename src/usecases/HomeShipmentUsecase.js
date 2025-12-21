function updateArrivalDate() {
  const { config, setting } = getConfigSettingAndToken();
  const homeShipmentSheet = new HomeShipmentSheet(config.SHEET_ID, config.HOME_SHIPMENT_SHEET_NAME);
  homeShipmentSheet.getActiveRowData();
  const trackingNumbers = homeShipmentSheet.getValues('追跡番号');
  const purchaseSheet = new PurchaseSheet(config.SHEET_ID, config.PURCHASE_SHEET_NAME, setting);
  const today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd');
  purchaseSheet.filter("追跡番号",trackingNumbers);
  purchaseSheet.writeColumn('自宅到着日', today);
}

function createInboundPlanFromHomeShipmentSheet() {
  const { config, setting, accessToken } = getConfigSettingAndToken();

  // 1. HomeShipmentSheetでアクティブな行の行番号列を取得
  const homeSheet = new HomeShipmentSheet(config.SHEET_ID, config.HOME_SHIPMENT_SHEET_NAME);
  const rowNumbers = homeSheet.getActiveRowNumbers();
  
  if (rowNumbers.length === 0) {
    throw new Error('選択された行に有効な行番号がありません');
  }

  // 2. 行番号のリストからPurchaseSheetのデータをフィルタ
  const purchaseSheet = new PurchaseSheet(config.SHEET_ID, config.PURCHASE_SHEET_NAME, setting);
  purchaseSheet.filter("行番号", rowNumbers);

  // 3. createInboundPlanForRowsで納品プランを作成
  const result = createInboundPlanForRows(purchaseSheet, accessToken);
  console.log(`Inbound plan created from HomeShipmentSheet: inboundPlanId=${result.inboundPlanId}, operationId=${result.operationId}, link=${result.link}`);
  return result;
}