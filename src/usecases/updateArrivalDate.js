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