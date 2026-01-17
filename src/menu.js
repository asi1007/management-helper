/* exported onOpen, showPackingInfoDialogFromButton, createInboundPlanFromActiveRows */

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('カスタムメニュー')
    .addItem('納品プラン作成', 'createInboundPlanFromActiveRows')
    .addItem('荷物情報入力', 'setPackingInfoFromActiveRow')
    .addItem('指示書作成', 'createInspectionSheetFromActiveRows')
    .addItem('ラベル印刷', 'printLabelsFromActiveRows')
    .addToUi();
}

function showPackingInfoDialogFromButton() {
  setPackingInfoFromActiveRow();
}
