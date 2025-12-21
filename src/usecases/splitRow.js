function splitRow() {
  const { config, setting } = getConfigSettingAndToken();
  const purchaseSheet = new PurchaseSheet(config.SHEET_ID, config.PURCHASE_SHEET_NAME, setting);
  const data = purchaseSheet.getActiveRowData();

  if (data.length === 0) {
    throw new Error('行が選択されていません');
  }

  if (data.length > 1) {
    throw new Error('1行のみ選択してください');
  }

  // ユーザーに納品数を入力してもらう
  const response = Browser.inputBox(
    '納品数の入力',
    'いくつ納品しますか？',
    Browser.Buttons.OK_CANCEL
  );

  if (response === 'cancel') {
    return;
  }

  const deliveryQuantity = Number(response);
  if (isNaN(deliveryQuantity) || deliveryQuantity <= 0) {
    throw new Error('有効な数値を入力してください');
  }

  // 購入数（数量）の列インデックスを取得
  const quantityColumnIndex = setting.get('数量');
  const originalRowNumber = purchaseSheet.rowNumbers[0];
  const originalQuantity = Number(data[0][quantityColumnIndex]);

  if (isNaN(originalQuantity) || originalQuantity <= 0) {
    throw new Error('購入数が無効です');
  }

  if (deliveryQuantity >= originalQuantity) {
    throw new Error(`納品数は購入数（${originalQuantity}）未満である必要があります`);
  }

  // 元の行の下に新しい行を挿入
  purchaseSheet.sheet.insertRowAfter(originalRowNumber);
  const newRowNumber = originalRowNumber + 1;

  // 元の行の全列を新しい行にコピー
  const lastColumn = purchaseSheet.sheet.getLastColumn();
  const sourceRange = purchaseSheet.sheet.getRange(originalRowNumber, 1, 1, lastColumn);
  const targetRange = purchaseSheet.sheet.getRange(newRowNumber, 1, 1, lastColumn);
  sourceRange.copyTo(targetRange);

  // 元の行の購入数を「購入数 - 納品数」に更新
  const remainingQuantity = originalQuantity - deliveryQuantity;
  const quantityColumn = quantityColumnIndex + 1;
  purchaseSheet.sheet.getRange(originalRowNumber, quantityColumn).setValue(remainingQuantity);

  // 新しい行の購入数を「納品数」に設定
  purchaseSheet.sheet.getRange(newRowNumber, quantityColumn).setValue(deliveryQuantity);

  console.log(`行${originalRowNumber}を分割しました: 残り${remainingQuantity}個、納品${deliveryQuantity}個`);
}

