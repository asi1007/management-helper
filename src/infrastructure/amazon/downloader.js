/* exported Downloader */

class Downloader{
  constructor(authToken){
    this.SP_API_URL = "https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20/items/labels";
    this.MAX_QUANTITY_PER_REQUEST = 999;
    this.authToken = authToken;
    this.options = {
      method: 'post',
      muteHttpExceptions : true,
      headers: {
        "Accept" : "application/json",
        "x-amz-access-token": authToken,
        "Content-Type" : "application/json"
      }
    };
  }

  downloadLabels(skuNums, fileName){
    const chunks = this._splitByQuantityLimit(skuNums);
    const folder = DriveApp.getFolderById("1ymbSzyiawRaREUwwaNYp4OzoGEOBgDNp");
    const totalChunks = chunks.length;

    if (totalChunks === 1) {
      return this._downloadSingleBatch(chunks[0], fileName, folder);
    }

    return this._downloadMultipleBatches(chunks, fileName, folder);
  }

  _downloadSingleBatch(skuNums, fileName, folder) {
    const responseJson = this._fetchLabels(skuNums);
    const pdfBlob = this._downloadPdfBlob(responseJson);
    const file = folder.createFile(pdfBlob.setName(fileName + '.pdf'));
    const downloadUrl = `https://drive.google.com/uc?export=download&id=${file.getId()}`;

    return { url: downloadUrl, responseData: responseJson };
  }

  _downloadMultipleBatches(chunks, fileName, folder) {
    const urls = [];
    let lastResponseJson = null;

    for (let i = 0; i < chunks.length; i++) {
      console.log(`ラベル分割ダウンロード: ${i + 1}/${chunks.length}`);
      const responseJson = this._fetchLabels(chunks[i]);
      const pdfBlob = this._downloadPdfBlob(responseJson);
      const partName = `${fileName}_part${i + 1}`;
      const file = folder.createFile(pdfBlob.setName(partName + '.pdf'));
      urls.push(`https://drive.google.com/uc?export=download&id=${file.getId()}`);
      lastResponseJson = responseJson;
    }

    console.log(`ラベル分割ダウンロード完了: ${chunks.length}件のPDFを作成しました`);
    return { url: urls[0], urls: urls, responseData: lastResponseJson };
  }

  _fetchLabels(skuNums) {
    const payload = {
      labelType: 'STANDARD_FORMAT',
      marketplaceId: 'A1VC38T7YXB528',
      mskuQuantities: skuNums,
      localeCode: "ja_JP",
      pageType: 'A4_40_52x29'
    };

    const options = Object.assign({}, this.options, {
      payload: JSON.stringify(payload)
    });

    const response = UrlFetchApp.fetch(this.SP_API_URL, options);
    const responseJson = JSON.parse(response.getContentText());
    console.log('downloadLabels response:', responseJson);

    if (responseJson.errors && responseJson.errors.length > 0) {
      const errorMessages = responseJson.errors.map(e => `${e.code}: ${e.message}`).join('; ');
      throw new Error(`SP-API ラベル取得エラー: ${errorMessages}`);
    }

    if (!responseJson.documentDownloads || responseJson.documentDownloads.length === 0) {
      throw new Error('SP-API レスポンスにダウンロードURLが含まれていません');
    }

    return responseJson;
  }

  _downloadPdfBlob(responseJson) {
    const fileURI = responseJson.documentDownloads[0].uri;
    const fileResponse = UrlFetchApp.fetch(fileURI, {method:"GET"});
    return fileResponse.getBlob();
  }

  _splitByQuantityLimit(skuNums) {
    const maxQty = this.MAX_QUANTITY_PER_REQUEST;
    const totalQuantity = skuNums.reduce((sum, item) => sum + item.quantity, 0);

    if (totalQuantity <= 15000) {
      return [skuNums];
    }

    const chunks = [];
    const currentChunk = [];
    let expanded = [];

    for (const item of skuNums) {
      if (item.quantity <= maxQty) {
        expanded.push(item);
      } else {
        let remaining = item.quantity;
        while (remaining > 0) {
          const qty = Math.min(remaining, maxQty);
          expanded.push({ msku: item.msku, quantity: qty });
          remaining -= qty;
        }
      }
    }

    let chunkTotal = 0;
    for (const item of expanded) {
      if (chunkTotal + item.quantity > maxQty && currentChunk.length > 0) {
        chunks.push([...currentChunk]);
        currentChunk.length = 0;
        chunkTotal = 0;
      }
      currentChunk.push(item);
      chunkTotal += item.quantity;
    }

    if (currentChunk.length > 0) {
      chunks.push(currentChunk);
    }

    console.log(`ラベル数量が上限(${maxQty})を超えるため ${chunks.length} 回に分割します`);
    return chunks;
  }
}
