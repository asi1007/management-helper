function updateArrivalDate() {
  const { config, setting } = getConfigSettingAndToken();
  const homeShipmentSheet = new HomeShipmentSheet(config.SHEET_ID, config.HOME_SHIPMENT_SHEET_NAME, setting);
  const purchaseSheet = new PurchaseSheet(config.SHEET_ID, config.PURCHASE_SHEET_NAME, setting);

  const activeSheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const activeRange = activeSheet.getActiveRange();
  
  if (activeSheet.getName() !== config.HOME_SHIPMENT_SHEET_NAME) {
    throw new Error('自宅発送用シートで実行してください');
  }

  // アクティブセルの行の追跡番号を取得
  const trackingNumberColumnIndex = setting.get('追跡番号') + 1;
  const activeRowIndex = activeRange.getRow();
  const trackingNumber = activeSheet.getRange(activeRowIndex, trackingNumberColumnIndex).getValue();

  if (!trackingNumber) {
    throw new Error('追跡番号が見つかりません');
  }

  console.log(`追跡番号: ${trackingNumber} を処理します`);

  // 同じ追跡番号のすべての行番号を取得（自宅発送シート内）
  const homeShipmentRowNums = homeShipmentSheet.getRowNumsByTracking(trackingNumber);
  console.log(`対象行番号(自宅発送シート): ${homeShipmentRowNums.join(', ')}`);

  // 仕入管理シートの同じ行番号の「自宅到着日」に日付を書き込み
  // 自宅発送シートと仕入管理シートは行が同期している（同じ行番号が同じ商品を指す）という前提
  const today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd');
  const arrivalDateColumnIndex = setting.get('自宅到着日') + 1;

  let successCount = 0;
  for (const rowNum of homeShipmentRowNums) {
    try {
      purchaseSheet.writeCell(rowNum, arrivalDateColumnIndex, today);
      successCount++;
    } catch (e) {
      console.error(`行番号 ${rowNum} への書き込みに失敗: ${e.message}`);
    }
  }

  console.log(`${successCount}件の更新が完了しました`);
  SpreadsheetApp.getUi().alert(`${successCount}件の自宅到着日を更新しました\n追跡番号: ${trackingNumber}`);
}