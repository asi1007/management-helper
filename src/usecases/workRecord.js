function recordWorkStart() {
  const { config } = getConfigSettingAndToken();
  
  // 自宅発送シートでアクティブな行のデータを取得
  const homeSheet = new HomeShipmentSheet(config.SHEET_ID, config.HOME_SHIPMENT_SHEET_NAME);
  const activeData = homeSheet.getActiveRowData();
  
  if (activeData.length === 0) {
    throw new Error('選択された行がありません');
  }
  
  // ASINと購入日の列インデックスを取得
  const asinColumnIndex = homeSheet._getColumnIndex("ASIN");
  const purchaseDateColumnIndex = homeSheet._getColumnIndex("購入日");
  
  // 作業記録シートに追加
  const workRecordSheet = new WorkRecordSheet(config.SHEET_ID, config.WORK_RECORD_SHEET_NAME);
  const timestamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');
  
  for (const row of activeData) {
    const asin = row[asinColumnIndex];
    const purchaseDate = row[purchaseDateColumnIndex];
    
    if (!asin) {
      console.warn(`ASINが空の行をスキップしました`);
      continue;
    }
    
    workRecordSheet.appendRecord(asin, purchaseDate, "開始", timestamp);
  }
  
  console.log(`${activeData.length}件の作業記録（開始）を追加しました`);
}

function recordWorkEnd() {
  const { config } = getConfigSettingAndToken();
  
  // 自宅発送シートでアクティブな行のデータを取得
  const homeSheet = new HomeShipmentSheet(config.SHEET_ID, config.HOME_SHIPMENT_SHEET_NAME);
  const activeData = homeSheet.getActiveRowData();
  
  if (activeData.length === 0) {
    throw new Error('選択された行がありません');
  }
  
  // ASINと購入日の列インデックスを取得
  const asinColumnIndex = homeSheet._getColumnIndex("ASIN");
  const purchaseDateColumnIndex = homeSheet._getColumnIndex("購入日");
  
  // 作業記録シートに追加
  const workRecordSheet = new WorkRecordSheet(config.SHEET_ID, config.WORK_RECORD_SHEET_NAME);
  const timestamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');
  
  for (const row of activeData) {
    const asin = row[asinColumnIndex];
    const purchaseDate = row[purchaseDateColumnIndex];
    
    if (!asin) {
      console.warn(`ASINが空の行をスキップしました`);
      continue;
    }
    
    workRecordSheet.appendRecord(asin, purchaseDate, "終了", timestamp);
  }
  
  console.log(`${activeData.length}件の作業記録（終了）を追加しました`);
}

