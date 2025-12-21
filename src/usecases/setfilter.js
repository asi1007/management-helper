function chfilter() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // E2の値を取得
  const filterValue = sheet.getRange("E2").getValue();

  // D4のフィルタがある範囲を特定
  const range = sheet.getRange("D4").getDataRegion(); // D4を含むデータ範囲
  const filter = range.getFilter() || range.createFilter();

  // フィルタ条件を設定
  const columnPosition = 4; // D列を基準範囲の1列目とする
  const criteria = SpreadsheetApp.newFilterCriteria()
    .whenTextContains(filterValue)
    .build();

  // 既存条件をクリアして再設定
  filter.removeColumnFilterCriteria(columnPosition);
  filter.setColumnFilterCriteria(columnPosition, criteria);
}