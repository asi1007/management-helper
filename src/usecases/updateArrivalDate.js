function updateArrivalDate() {
  const { config, setting } = getConfigSettingAndToken();
  const homeShipmentSheet = new HomeShipmentSheet(config.SHEET_ID, config.HOME_SHIPMENT_SHEET_NAME, setting);
  const purchaseSheet = new PurchaseSheet(config.SHEET_ID, config.PURCHASE_SHEET_NAME, setting);

  // アクティブセルの行の追跡番号と行番号（ID）を取得
  const rowId = homeShipmentSheet.getActiveRowValue('行番号');
  console.log(`取得した行ID: ${rowId}`);
  
  const trackingNumber = homeShipmentSheet.getActiveRowValue('追跡番号');

  if (!trackingNumber) {
    throw new Error('追跡番号が見つかりません');
  }

  console.log(`追跡番号: ${trackingNumber} を処理します`);

  // 同じ追跡番号のすべての行番号(ID)を取得（自宅発送シート内）
  const homeShipmentRowIds = homeShipmentSheet.getRowIdsByTracking(trackingNumber);
  console.log(`対象行ID(自宅発送シート): ${homeShipmentRowIds.join(', ')}`);

  // 仕入管理シートの同じ行番号(ID)を持つ行の「自宅到着日」に日付を書き込み
  const today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd');
  const arrivalDateColumnIndex = setting.get('自宅到着日') + 1; // 列番号は設定から取得（1始まり）

  let successCount = 0;
  for (const targetRowId of homeShipmentRowIds) {
    try {
      // IDから仕入管理シート上の実際の行番号を検索
      const targetRowNum = purchaseSheet.getRowNum('行番号', targetRowId);
      
      if (targetRowNum) {
        purchaseSheet.writeCell(targetRowNum, arrivalDateColumnIndex, today);
        successCount++;
      } else {
        console.warn(`行ID ${targetRowId} が仕入管理シートで見つかりませんでした`);
      }
    } catch (e) {
      console.error(`行ID ${targetRowId} への書き込みに失敗: ${e.message}`);
    }
  }

  console.log(`${successCount}件の更新が完了しました`);
  SpreadsheetApp.getUi().alert(`${successCount}件の自宅到着日を更新しました\n追跡番号: ${trackingNumber}`);
}