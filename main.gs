// ラベル・指示書
function generateLabelsAndInstructions() {
  return generateLabelsAndInstructions_();
}

// 納品プラン
function createInboundPlanFromActiveRows() {
  return createInboundPlanFromActiveRows_();
}

function createInboundPlanFromActiveRowsWithPlacementSelection() {
  return createInboundPlanFromActiveRowsWithPlacementSelection_();
}

function confirmPlacementOptionFromDialog(inboundPlanId, placementOptionId, allowPallet) {
  return confirmPlacementOptionFromDialog_(inboundPlanId, placementOptionId, allowPallet);
}

// 自宅発送
function createInboundPlanFromHomeShipmentSheet() {
  return createInboundPlanFromHomeShipmentSheet_();
}

// 作業記録
function recordWorkStart() {
  return recordWorkStart_();
}

function recordWorkEnd() {
  return recordWorkEnd_();
}

function recordDefect() {
  return recordDefect_();
}

// 検品シート
function createInspectionSheetFromPurchaseRowsIfNeeded(purchaseRows) {
  return createInspectionSheetFromPurchaseRowsIfNeeded_(purchaseRows);
}

// 在庫・ステータス推測値
function updateInventoryEstimateFromStockSheet() {
  return updateInventoryEstimateFromStockSheet_();
}

function updateStatusAndInventoryEstimate() {
  return updateStatusAndInventoryEstimate_();
}

function moveOutOfStockToArchive() {
  return moveOutOfStockToArchive_();
}

function updateStatusEstimateFromInboundPlans() {
  return updateStatusEstimateFromInboundPlans_();
}

// 行分割
function splitRow() {
  return splitRow_();
}

function promptDeliveryQuantity() {
  return promptDeliveryQuantity_();
}

// 到着日更新
function updateArrivalDate() {
  return updateArrivalDate_();
}

// フィルタ
function chfilter() {
  return chfilter_();
}

// 荷物情報
function setPackingInfoFromActiveRow() {
  return setPackingInfoFromActiveRow_();
}

function submitPackingInfoFromDialog(inboundPlanId, cartonInputText) {
  return submitPackingInfoFromDialog_(inboundPlanId, cartonInputText);
}
