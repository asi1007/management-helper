function createInboundPlanFromHomeShipmentSheet() {
  const config = getEnvConfig();
  const accessToken = getAuthToken();

  // 1. HomeShipmentSheetでアクティブな行の行番号列を取得
  const homeSheet = new HomeShipmentSheet(config.HOME_SHIPMENT_SHEET_NAME);
  const rowNumbers = homeSheet.getActiveRowNumbers();

  if (rowNumbers.length === 0) {
    throw new Error('選択された行に有効な行番号がありません');
  }

  // 2. 行番号のリストからPurchaseSheetのデータをフィルタ
  const purchaseSheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  purchaseSheet.filter("行番号", rowNumbers);

  // 3. createInboundPlanForRowsで納品プランを作成
  const result = createInboundPlanForRows(purchaseSheet, accessToken);
  console.log(`Inbound plan created from HomeShipmentSheet: inboundPlanId=${result.inboundPlanId}, operationId=${result.operationId}, link=${result.link}`);
  return result;
}



