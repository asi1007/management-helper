/* exported PurchaseSheet */

class PurchaseSheet extends BaseSheet {
  constructor(sheetName){
    // 仕入管理シートは1行目がヘッダー前提
    super(sheetName, 1, 1);
    this.rowNumbers = [];
  }

  setRowNumbers(rowNumbers){
    this.rowNumbers = rowNumbers;
  }

  filter(columnName, values) {
    console.log(`Filtering column "${columnName}" with values: ${JSON.stringify(values)}`);
    const columnIndex = this._getColumnIndexByName(columnName);
    const rowNumbers = [];
    const filteredData = [];
    
    for (let i = 0; i < this.data.length; i++) {
      const rowValue = String(this.data[i][columnIndex]);
      if (values.some(v => String(v) === rowValue)) {
        // BaseRow.rowNumber は実シート上の行番号
        rowNumbers.push(this.data[i].rowNumber);
        filteredData.push(this.data[i]);
      }
    }
    
    this.rowNumbers = rowNumbers;
    this.data = filteredData;
    console.log(`${columnName}でフィルタリング: ${rowNumbers.length}行が見つかりました`);
    return this.data;
  }

  writeColumn(columnName, value){
    try {
      const column = this._getColumnIndexByName(columnName) + 1;
      let successCount = 0;
      
      for (const rowNum of this.rowNumbers) {
          if (typeof value === 'object' && value.type === 'formula') {
            this.sheet.getRange(rowNum, column).setFormula(value.value);
          } else {
            this.sheet.getRange(rowNum, column).setValue(value);
          }
          successCount++;
      }
      console.log(`${columnName}を${successCount}行に書き込みました`);
    } catch (e) {
      console.warn(`${columnName}への書き込みに失敗しました: ${e.message}`);
      throw e;
    }
  }

  _generatePlanNameText() {
    const dateStr = this._formatDateMMDD(new Date());
    let deliveryCategory = '';
    try {
      deliveryCategory = this.data.length > 0 ? (this.data[0].get("納品分類") || '') : '';
    } catch (e) {
      deliveryCategory = '';
    }
    return `${dateStr}${deliveryCategory}`;
  }

  _formatDateMMDD(date) {
    const month = String(date.getMonth() + 1);
    const day = String(date.getDate());
    const monthStr = month.length === 1 ? '0' + month : month;
    const dayStr = day.length === 1 ? '0' + day : day;
    return `${monthStr}/${dayStr}`;
  }

  aggregateItems() {
    const aggregatedItems = {};
    const labelOwner = 'SELLER';
    
    for (let i = 0; i < this.data.length; i++) {
      const row = this.data[i];
      let sku = '';
      let asin = '';
      let quantity = 0;
      try { sku = row.get("sku") || ''; } catch (e) {}
      try { asin = row.get("ASIN") || ''; } catch (e) {}
      try { quantity = Number(row.get("数量")); } catch (e) { quantity = 0; }
      
      if (!sku || !quantity || quantity <= 0) {
        console.warn(`納品プラン対象外: sku=${sku}, quantity=${quantity}`);
        continue;
      }
      
      if (!aggregatedItems[sku]) {
        aggregatedItems[sku] = {
          msku: sku,
          asin: asin,
          quantity: 0,
          labelOwner: labelOwner
        };
      }
      aggregatedItems[sku].quantity += quantity;
    }
    
    return aggregatedItems;
  }

  writePlanResult(planResult) {
    if (planResult.link) {
      const displayText = planResult.inboundPlanId || this._generatePlanNameText();
      
      const linkFormula = `=HYPERLINK("${planResult.link}", "${displayText}")`;
      this.writeColumn("納品プラン", { type: 'formula', value: linkFormula });
    }
    
    const dateOnly = new Date();
    dateOnly.setHours(0, 0, 0, 0);
    this.writeColumn("発送日", dateOnly);
  }

  decreasePurchaseQuantity(quantity) {
    const quantityColumnIndex = this._getColumnIndexByName('数量');
    let successCount = 0;
    
    for (const rowNum of this.rowNumbers) {
      const currentQuantity = Number(this.sheet.getRange(rowNum, quantityColumnIndex + 1).getValue());
      const newQuantity = Math.max(0, currentQuantity - quantity);
      this.sheet.getRange(rowNum, quantityColumnIndex + 1).setValue(newQuantity);
      successCount++;
      console.log(`行${rowNum}: 購入数を${currentQuantity}から${newQuantity}に減らしました`);
    }
    
    console.log(`${successCount}行の購入数を${quantity}減らしました`);
  }

}
