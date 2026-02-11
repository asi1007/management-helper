function updateArrivalDate_() {
  console.log('[updateArrivalDate] start');
  try {
    const config = getEnvConfig();
    const homeShipmentSheet = new HomeShipmentSheet(config.HOME_SHIPMENT_SHEET_NAME);
    const activeRows = homeShipmentSheet.getActiveRowData();
    console.log(`[updateArrivalDate] selectedRows=${activeRows.length}`);

    const trackingNumbers = homeShipmentSheet.getValues('追跡番号');
    const uniqTracking = Array.from(new Set((trackingNumbers || []).map(v => String(v || '').trim()).filter(Boolean)));
    console.log(`[updateArrivalDate] trackingNumbers: raw=${(trackingNumbers || []).length}, uniqueNonEmpty=${uniqTracking.length}`);

    const purchaseSheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
    const today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd');
    console.log(`[updateArrivalDate] write 自宅到着日=${today} where 追跡番号 in [${uniqTracking.slice(0, 10).join(', ')}]${uniqTracking.length > 10 ? '...' : ''}`);

    purchaseSheet.filter("追跡番号", uniqTracking);
    purchaseSheet.writeColumn('自宅到着日', today);
    console.log('[updateArrivalDate] done');
  } catch (e) {
    console.error(`[updateArrivalDate] error: ${e && e.message ? e.message : String(e)}`);
    console.error(e && e.stack ? e.stack : '(no stack)');
    throw e;
  }
}