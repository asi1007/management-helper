/* exported InspectionMasterItem */

class InspectionMasterItem {
  /**
   * @param {string} asin
   * @param {string} inspectionPoint
   */
  constructor(asin, inspectionPoint) {
    this.asin = String(asin || '').trim();
    this.inspectionPoint = String(inspectionPoint || '').trim();
  }
}


