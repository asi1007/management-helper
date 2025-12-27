/* exported recordWorkStart, recordWorkEnd, recordDefect */

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

function recordDefect() {
  const { config, setting } = getConfigSettingAndToken();
  
  // 1. 自宅発送シートのS列から不良原因リストを読み込み
  const homeSheet = new HomeShipmentSheet(config.SHEET_ID, config.HOME_SHIPMENT_SHEET_NAME);
  const defectReasonList = homeSheet.getDefectReasonList();
  
  if (defectReasonList.length === 0) {
    Browser.msgBox('エラー', '不良原因リストが見つかりません。自宅発送シートのS列に不良原因を入力してください。', Browser.Buttons.OK);
    return;
  }
  
  // 2. 不良数、原因、コメントを記載するフォームを表示
  // 不良数の入力
  const quantityResponse = Browser.inputBox(
    '不良品登録',
    '不良数を入力してください:',
    Browser.Buttons.OK_CANCEL
  );
  
  if (quantityResponse === 'cancel') {
    return;
  }
  
  const defectQuantity = Number(quantityResponse);
  if (isNaN(defectQuantity) || defectQuantity <= 0) {
    Browser.msgBox('エラー', '有効な数値を入力してください。', Browser.Buttons.OK);
    return;
  }
  
  // 不良原因の選択
  const reasonListText = defectReasonList.map((reason, index) => `${index + 1}. ${reason}`).join('\n');
  const reasonPrompt = `不良原因を選択してください（番号を入力）:\n\n${reasonListText}`;
  const reasonResponse = Browser.inputBox(
    '不良品登録',
    reasonPrompt,
    Browser.Buttons.OK_CANCEL
  );
  
  if (reasonResponse === 'cancel') {
    return;
  }
  
  const reasonIndex = Number(reasonResponse) - 1;
  if (isNaN(reasonIndex) || reasonIndex < 0 || reasonIndex >= defectReasonList.length) {
    Browser.msgBox('エラー', '有効な番号を入力してください。', Browser.Buttons.OK);
    return;
  }
  
  const selectedReason = defectReasonList[reasonIndex];
  
  // コメントの入力（オプショナル）
  const commentResponse = Browser.inputBox(
    '不良品登録',
    'コメントを入力してください（任意）:',
    Browser.Buttons.OK_CANCEL
  );
  
  if (commentResponse === 'cancel') {
    return;
  }
  
  const comment = commentResponse || '';
  
  // 3. 該当行の行番号を取得
  const activeData = homeSheet.getActiveRowData();
  if (activeData.length === 0) {
    Browser.msgBox('エラー', '選択された行がありません。', Browser.Buttons.OK);
    return;
  }
  
  const rowNumbers = homeSheet.getActiveRowNumbers();
  if (rowNumbers.length === 0) {
    Browser.msgBox('エラー', '選択された行に有効な行番号がありません。', Browser.Buttons.OK);
    return;
  }
  
  // ASINと購入日の列インデックスを取得
  const asinColumnIndex = homeSheet._getColumnIndex("ASIN");
  const purchaseDateColumnIndex = homeSheet._getColumnIndex("購入日");
  
  // 4. 仕入管理シートの購入数を不良数分減らす
  const purchaseSheet = new PurchaseSheet(config.SHEET_ID, config.PURCHASE_SHEET_NAME, setting);
  purchaseSheet.filter("行番号", rowNumbers);
  
  if (purchaseSheet.data.length === 0) {
    Browser.msgBox('エラー', '仕入管理シートに対応する行が見つかりません。', Browser.Buttons.OK);
    return;
  }
  
  purchaseSheet.decreasePurchaseQuantity(defectQuantity);
  
  // 5. 作業記録にevent_type「不良」、数量に不良数を登録
  const workRecordSheet = new WorkRecordSheet(config.SHEET_ID, config.WORK_RECORD_SHEET_NAME);
  const timestamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');
  
  for (const row of activeData) {
    const asin = row[asinColumnIndex];
    const purchaseDate = row[purchaseDateColumnIndex];
    
    if (!asin) {
      console.warn(`ASINが空の行をスキップしました`);
      continue;
    }
    
    // ステータスは「不良」のみを記録し、原因とコメントは別の列に記録
    workRecordSheet.appendRecord(asin, purchaseDate, "不良", timestamp, defectQuantity, selectedReason, comment);
  }
  
  Browser.msgBox('完了', `不良品登録を完了しました。\n不良数: ${defectQuantity}\n原因: ${selectedReason}`, Browser.Buttons.OK);
  console.log(`${activeData.length}件の不良品記録を追加しました`);
}


