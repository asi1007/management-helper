/* exported InspectionMasterItem */

class InspectionMasterItem {
  /**
   * @param {string} asin
   * @param {string} productName
   * @param {string} inspectionPoint
   * @param {string} detailInstructionUrl
   */
  constructor(asin, productName, inspectionPoint, detailInstructionUrl = '') {
    this.asin = String(asin || '').trim();
    this.productName = String(productName || '').trim();
    this.inspectionPoint = String(inspectionPoint || '').trim();
    this.detailInstructionUrl = String(detailInstructionUrl || '').trim();
  }
}


