/* exported onOpen */

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('カスタムメニュー')
    .addItem('荷物情報入力', 'setPackingInfoFromActiveRow')
    .addItem('納品プラン作成（Placement選択）', 'createInboundPlanFromActiveRowsWithPlacementSelection')
    .addItem('指示書作成', 'createInspectionSheetFromActiveRows')
    .addItem('ラベル印刷', 'printLabelsFromActiveRows')
    .addToUi();
}
