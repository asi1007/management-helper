/* exported recordWorkStart, recordWorkEnd, recordDefect */

function recordWorkStart() {
  const { config } = getConfigSettingAndToken();
  
  // 自宅発送シートでアクティブな行のデータを取得
  const homeSheet = new HomeShipmentSheet(config.HOME_SHIPMENT_SHEET_NAME);
  const activeData = homeSheet.getActiveRowData();
  
  if (activeData.length === 0) {
    throw new Error('選択された行がありません');
  }
  
  // 作業記録シートに追加
  console.log(`作業記録シート名: ${config.WORK_RECORD_SHEET_NAME}`);
  const workRecordSheet = new WorkRecordSheet(config.WORK_RECORD_SHEET_NAME);
  const timestamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');
  
  for (const row of activeData) {
    const asin = row.get("ASIN");
    const purchaseDate = row.get("購入日");
    let orderNumber = '';
    try { orderNumber = row.get("注文番号") || ''; } catch (e) {}
    
    if (!asin) {
      console.warn(`ASINが空の行をスキップしました`);
      continue;
    }
    
    workRecordSheet.appendRecord(asin, purchaseDate, "開始", timestamp, null, null, null, orderNumber);
  }
  
  console.log(`${activeData.length}件の作業記録（開始）を追加しました`);
}

function recordWorkEnd() {
  const { config } = getConfigSettingAndToken();
  
  // 自宅発送シートでアクティブな行のデータを取得
  const homeSheet = new HomeShipmentSheet(config.HOME_SHIPMENT_SHEET_NAME);
  const activeData = homeSheet.getActiveRowData();
  
  if (activeData.length === 0) {
    throw new Error('選択された行がありません');
  }
  
  // 作業記録シートに追加
  console.log(`作業記録シート名: ${config.WORK_RECORD_SHEET_NAME}`);
  const workRecordSheet = new WorkRecordSheet(config.WORK_RECORD_SHEET_NAME);
  const timestamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');
  
  for (const row of activeData) {
    const asin = row.get("ASIN");
    const purchaseDate = row.get("購入日");
    let orderNumber = '';
    try { orderNumber = row.get("注文番号") || ''; } catch (e) {}
    
    if (!asin) {
      console.warn(`ASINが空の行をスキップしました`);
      continue;
    }
    
    workRecordSheet.appendRecord(asin, purchaseDate, "終了", timestamp, null, null, null, orderNumber);
  }
  
  console.log(`${activeData.length}件の作業記録（終了）を追加しました`);
}

function recordDefect() {
  const config = getEnvConfig();
  const ui = SpreadsheetApp.getUi();

  // 1. 自宅発送シートのS列から不良原因リストを読み込み
  const homeSheet = new HomeShipmentSheet(config.HOME_SHIPMENT_SHEET_NAME);
  const defectReasonList = homeSheet.getDefectReasonList();

  if (defectReasonList.length === 0) {
    ui.alert('エラー', '不良原因リストが見つかりません。自宅発送シートのS列に不良原因を入力してください。', ui.ButtonSet.OK);
    return;
  }

  // 2. 該当行の行番号を取得
  const activeData = homeSheet.getActiveRowData();
  if (activeData.length === 0) {
    ui.alert('エラー', '選択された行がありません。', ui.ButtonSet.OK);
    return;
  }

  // BaseRow(row) から直接、実シート上の行番号を取得する
  const rowNumbers = activeData.map(row => row.rowNumber).filter(rn => rn !== null && rn !== undefined && rn !== '');
  if (rowNumbers.length === 0) {
    ui.alert('エラー', '選択された行に有効な行番号がありません。', ui.ButtonSet.OK);
    return;
  }

  // 仕入管理シートの行番号とASIN/購入日/注文番号を取得
  const rowInfo = activeData.map(row => {
    let orderNumber = '';
    try { orderNumber = row.get("注文番号") || ''; } catch (e) {}
    return {
      homeRowNumber: row.rowNumber,
      purchaseRowNumber: row.get("行番号"),
      asin: row.get("ASIN"),
      purchaseDate: row.get("購入日"),
      orderNumber: orderNumber
    };
  }).filter(info => info.purchaseRowNumber);

  // 3. 不良数を入力
  const quantityResponse = ui.prompt('不良品登録', '不良数を入力してください:', ui.ButtonSet.OK_CANCEL);
  if (quantityResponse.getSelectedButton() !== ui.Button.OK) {
    return;
  }
  const quantity = parseInt(quantityResponse.getResponseText());
  if (isNaN(quantity) || quantity <= 0) {
    ui.alert('エラー', '有効な不良数を入力してください。', ui.ButtonSet.OK);
    return;
  }

  // 4. 原因を選択（番号で入力）
  const reasonList = defectReasonList.map((r, i) => `${i + 1}: ${r}`).join('\n');
  const reasonResponse = ui.prompt('不良品登録', `原因を番号で選択してください:\n${reasonList}`, ui.ButtonSet.OK_CANCEL);
  if (reasonResponse.getSelectedButton() !== ui.Button.OK) {
    return;
  }
  const reasonIndex = parseInt(reasonResponse.getResponseText()) - 1;
  if (isNaN(reasonIndex) || reasonIndex < 0 || reasonIndex >= defectReasonList.length) {
    ui.alert('エラー', '有効な番号を入力してください。', ui.ButtonSet.OK);
    return;
  }
  const selectedReason = defectReasonList[reasonIndex];

  // 5. コメント（任意）
  const commentResponse = ui.prompt('不良品登録', 'コメント（任意、空欄可）:', ui.ButtonSet.OK_CANCEL);
  if (commentResponse.getSelectedButton() !== ui.Button.OK) {
    return;
  }
  const comment = commentResponse.getResponseText() || null;

  // 6. 処理実行
  const purchaseRowNumbers = rowInfo.map(info => info.purchaseRowNumber);

  // 仕入管理シートの購入数を不良数分減らす
  const purchaseSheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  purchaseSheet.filter("行番号", purchaseRowNumbers);

  if (purchaseSheet.data.length === 0) {
    ui.alert('エラー', '仕入管理シートに対応する行が見つかりません。', ui.ButtonSet.OK);
    return;
  }

  const zeroQuantityRows = purchaseSheet.decreasePurchaseQuantity(quantity);

  // 購入数が0になった行を削除
  if (zeroQuantityRows.length > 0) {
    purchaseSheet.deleteRows(zeroQuantityRows);
  }

  // 作業記録に登録
  const workRecordSheet = new WorkRecordSheet(config.WORK_RECORD_SHEET_NAME);
  const timestamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');

  for (const info of rowInfo) {
    const asin = info.asin;
    const purchaseDate = info.purchaseDate;
    const orderNumber = info.orderNumber || '';

    if (!asin) {
      console.warn(`ASINが空の行をスキップしました`);
      continue;
    }

    workRecordSheet.appendRecord(asin, purchaseDate, "不良", timestamp, quantity, selectedReason, comment, orderNumber);
  }

  console.log(`${rowInfo.length}件の不良品記録を追加しました`);
  ui.alert('完了', `不良品登録を完了しました。\n不良数: ${quantity}\n原因: ${selectedReason}`, ui.ButtonSet.OK);
}
