/* exported InstructionSheet */

class InstructionSheet {
  constructor(setting) {
    this.setting = setting;
    this.TEMPLATE_ID = '1YDBbEgxTnRZRqKi5UUsQAZfCgakdzVKNJtX6cPBZARA';
    this.START_ROW = 8;
    this.KEEPA_API_ENDPOINT = 'https://api.keepa.com/product';
    this.AMAZON_IMAGE_BASE_URL = 'https://images-na.ssl-images-amazon.com/images/I/';
  }

  create(data) {
    if (!Array.isArray(data) || data.length === 0) {
      throw new Error('指示書作成対象の行データが空、または不正です');
    }

    const rows = this._extractRows(data);
    const planName = this._generatePlanName(data);
    const sheetFile = this._createSheetFile(planName);
    this._writeRowData(sheetFile.sheet, rows);
    
    return `https://docs.google.com/spreadsheets/d/${sheetFile.fileId}/export?format=xlsx`;
  }

  _extractRows(data) {
    return data.map(row => [
      row[this.setting.get("fnsku")],
      row[this.setting.get("asin")],
      row[this.setting.get("数量")],
      row[this.setting.get("備考")],
      row[this.setting.get("注文依頼番号")]
    ]);
  }

  _generatePlanName(data) {
    const deliveryCategoryColumn = this.setting.getOptional ? this.setting.getOptional("納品分類") : null;
    const dateStr = this._formatDateMMDD(new Date());
    const deliveryCategory = data.length > 0 && deliveryCategoryColumn !== null 
      ? (data[0][deliveryCategoryColumn] || '') 
      : '';
    return `${dateStr}${deliveryCategory}`;
  }

  _createSheetFile(planName) {
    const originalFile = DriveApp.getFileById(this.TEMPLATE_ID);
    const fileId = originalFile.makeCopy(planName).getId();
    const sheet = SpreadsheetApp.openById(fileId).getActiveSheet();
    return { fileId, sheet };
  }

  _writeRowData(sheet, rows) {
    let rowNum = this.START_ROW;
    
    for (const row of rows) {
      sheet.getRange(rowNum, 2, 1, 5).setValues([row]);
      const asin = row[1]; // ASINは2列目
      const imageUrl = this._getProductImage(asin);
      if (imageUrl) {
        const blob = UrlFetchApp.fetch(imageUrl).getBlob();
        sheet.insertImage(blob, 1, rowNum);
      }
      rowNum++;
    }
  }

  _getProductImage(asin) {
    if (!asin) {
      return null;
    }
    
    const config = getEnvConfig();
    const url = `${this.KEEPA_API_ENDPOINT}?key=${config.KEEPA_API_KEY}&domain=5&asin=${asin}`;
    const params = {
      method: 'get',
      muteHttpExceptions: true
    };
    
    try {
      const response = UrlFetchApp.fetch(url, params);
      const json = JSON.parse(response.getContentText());
      
      if (json.error) {
        console.warn(`Keepa API error for ASIN ${asin}: ${json.error.message}`);
        return null;
      }
      
      if (!json.products || json.products.length === 0) {
        return null;
      }
      
      const product = json.products[0];
      const imagesCSV = product.imagesCSV;
      
      if (!imagesCSV) {
        return null;
      }
      
      const firstImageFile = imagesCSV.split(',')[0];
      return `${this.AMAZON_IMAGE_BASE_URL}${firstImageFile}._SL100_.jpg`;
    } catch (error) {
      console.error(`Failed to fetch image for ASIN ${asin}: ${error.message}`);
      return null;
    }
  }

  _formatDateMMDD(date) {
    const month = String(date.getMonth() + 1);
    const day = String(date.getDate());
    const monthStr = month.length === 1 ? '0' + month : month;
    const dayStr = day.length === 1 ? '0' + day : day;
    return `${monthStr}/${dayStr}`;
  }
}

