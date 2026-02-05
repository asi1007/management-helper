/* exported PurchaseSheet */

class PurchaseSheet extends BaseSheet {
  constructor(sheetName){
    // 仕入管理シートは4行目がヘッダー前提
    super(sheetName, 4, 1);
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
      try { sku = row.get("SKU") || ''; } catch (e) {}
      try { asin = row.get("ASIN") || ''; } catch (e) {}
      try { quantity = Number(row.get("購入数")); } catch (e) { quantity = 0; }
      
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
    const planCol = this._getColumnIndexByName("納品プラン") + 1;
    const shipDateCol = this._getColumnIndexByName("発送日") + 1;

    const link = planResult && planResult.link ? String(planResult.link) : '';
    const inboundPlanId = planResult && planResult.inboundPlanId ? String(planResult.inboundPlanId) : '';

    const dateOnly = new Date();
    dateOnly.setHours(0, 0, 0, 0);
    const dateStr = Utilities.formatDate(dateOnly, 'Asia/Tokyo', 'yyyy/MM/dd');

    for (const rowNum of this.rowNumbers) {
      // 納品プラン
      if (link) {
        const displayText = inboundPlanId || this._generatePlanNameText();
        const linkFormula = `=HYPERLINK("${link}", "${displayText}")`;
        const r = this.sheet.getRange(rowNum, planCol);
        r.setFormula(linkFormula);
        console.log(`[納品プラン] wrote ${r.getA1Notation()} formula=${linkFormula}`);
      } else if (inboundPlanId) {
        const r = this.sheet.getRange(rowNum, planCol);
        r.setValue(inboundPlanId);
        console.log(`[納品プラン] wrote ${r.getA1Notation()} value=${inboundPlanId}`);
      } else {
        console.log(`[納品プラン] skip row=${rowNum} (no link/inboundPlanId)`);
      }

      // 発送日
      const d = this.sheet.getRange(rowNum, shipDateCol);
      d.setValue(dateOnly);
      console.log(`[発送日] wrote ${d.getA1Notation()} value=${dateStr}`);
    }
  }

  decreasePurchaseQuantity(quantity) {
    const quantityColumnIndex = this._getColumnIndexByName('購入数');
    let successCount = 0;
    const zeroQuantityRows = [];

    for (const rowNum of this.rowNumbers) {
      const currentQuantity = Number(this.sheet.getRange(rowNum, quantityColumnIndex + 1).getValue());
      const newQuantity = Math.max(0, currentQuantity - quantity);
      this.sheet.getRange(rowNum, quantityColumnIndex + 1).setValue(newQuantity);
      successCount++;
      console.log(`行${rowNum}: 購入数を${currentQuantity}から${newQuantity}に減らしました`);

      if (newQuantity === 0) {
        zeroQuantityRows.push(rowNum);
      }
    }

    console.log(`${successCount}行の購入数を${quantity}減らしました`);
    return zeroQuantityRows;
  }

  deleteRows(rowNumbers) {
    if (!rowNumbers || rowNumbers.length === 0) {
      return;
    }

    const sortedRows = rowNumbers.slice().sort((a, b) => b - a);

    for (const rowNum of sortedRows) {
      this.sheet.deleteRow(rowNum);
      console.log(`行${rowNum}を削除しました`);
    }

    console.log(`${sortedRows.length}行を削除しました`);
  }

  /**
   * FNSKU補完（SKU -> FNSKU）
   * @param {string} accessToken
   * @param {BaseRow[]|null} targetRows 省略時はthis.data全体。指定時はその行だけ補完する。
   */
  fetchMissingFnskus(accessToken, targetRows = null) {
    const fnskuGetter = new FnskuGetter(accessToken);
    const fnskuColIndex = this._getColumnIndexByName("FNSKU");
    const fnskuCol = fnskuColIndex + 1;

    const strict = Array.isArray(targetRows);
    const rowsToProcess = strict ? targetRows : this.data;

    for (const row of rowsToProcess) {
      const fnsku = row.get("FNSKU");
      const sku = row.get("SKU");
      const rowNum = row.rowNumber;

      if (!fnsku || fnsku === '') {
        // #region agent log
        try{UrlFetchApp.fetch('http://127.0.0.1:7243/ingest/24045cd5-2584-4703-ab97-0442e02ed8a6',{method:'post',contentType:'application/json',payload:JSON.stringify({location:'purchaseSheet.js:PurchaseSheet.fetchMissingFnskus:before',message:'about to call getFnsku',data:{rowNum:rowNum,skuRaw:String(sku||''),skuTrim:String(sku||'').trim(),skuHasWhitespace:/\\s/.test(String(sku||'')),skuHasLeadingOrTrailingWhitespace:/^\\s|\\s$/.test(String(sku||''))},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'B'})});}catch(e){}
        try {
          const raw = String(sku ?? '');
          console.log(`[DBG][FNSKU][fetchMissingFnskus] rowNum=${rowNum} skuRaw=${JSON.stringify(raw)} skuTrim=${JSON.stringify(raw.trim())} skuCharCodesHead=${JSON.stringify(raw.slice(0,50).split('').map(c=>c.charCodeAt(0)))}`);
        } catch (e) {}
        // #endregion

        const skuTrim = String(sku || '').trim();
        if (!skuTrim) {
          console.warn(`[FNSKU補完] SKUが空のためFNSKU補完できません: row=${rowNum}`);
          if (strict) {
            throw new Error(`SKUが空のためFNSKU補完できません。行${rowNum}のSKU（またはASIN->SKU補完）を確認してください。`);
          }
          continue;
        }

        const fetchedFnsku = fnskuGetter.getFnsku(skuTrim);
        console.log(`Fetched FNSKU for ${sku}: ${fetchedFnsku}`);
        if (rowNum && fnskuCol >= 1) {
          this.writeCell(rowNum, fnskuCol, fetchedFnsku);
          // 指示書作成は this.data を参照するため、メモリ上の行データも更新する
          row[fnskuColIndex] = fetchedFnsku;
        }
      }
    }
  }

  /**
   * 指示書作成前の補完: SKUが空の場合、ASINから出品レポートでSKUを解決して書き戻す
   * @param {string} accessToken
   * @param {BaseRow[]|null} targetRows 省略時はthis.data全体が対象。指定時はその行だけを補完する（参照はシート全体）。
   */
  fillMissingSkusFromAsins(accessToken, targetRows = null) {
    const resolver = new MerchantListingsSkuResolver(accessToken);
    const skuColIndex = this._getColumnIndexByName("SKU");
    const skuCol = skuColIndex + 1;

    const asinToSkuLocal = this._buildAsinToSkuLocalMap_();
    const { targets } = this._collectMissingSkuTargets_(targetRows);

    if (targets.length === 0) {
      console.log('[SKU補完] SKU空白なし -> スキップ');
      return;
    }

    // 1) 仕入管理シート内の既存行のSKUを流用
    let filledByLocal = 0;
    const stillMissingAsins = [];
    for (const t of targets) {
      const resolvedLocal = asinToSkuLocal.get(t.asin);
      if (!resolvedLocal) {
        stillMissingAsins.push(t.asin);
        continue;
      }
      if (t.rowNum && skuCol >= 1) {
        this.writeCell(t.rowNum, skuCol, resolvedLocal);
        t.row[skuColIndex] = resolvedLocal; // in-memoryも更新
        filledByLocal++;
      }
    }

    // 2) まだ無い分だけ Reports API で解決
    const uniqueMissing = Array.from(new Set(stillMissingAsins));
    if (uniqueMissing.length === 0) {
      console.log(`[SKU補完] ローカル流用で全件補完: ${filledByLocal}/${targets.length}`);
      return;
    }

    console.log(`[SKU補完] ローカル流用=${filledByLocal}/${targets.length} -> Reports APIで解決開始 (ASIN数=${uniqueMissing.length})`);
    const asinToSkuRemote = resolver.resolveSkusByAsins(uniqueMissing);

    let filledByRemote = 0;
    for (const t of targets) {
      const currentSku = String(t.row.get("SKU") || '').trim();
      if (currentSku) continue;
      const resolved = asinToSkuRemote.get(t.asin);
      if (!resolved) continue;
      if (t.rowNum && skuCol >= 1) {
        this.writeCell(t.rowNum, skuCol, resolved);
        t.row[skuColIndex] = resolved;
        filledByRemote++;
      }
    }
    console.log(`[SKU補完] 書き込み完了: local=${filledByLocal}, remote=${filledByRemote}, total=${filledByLocal + filledByRemote}/${targets.length}`);
  }

  /**
   * 仕入管理シート全体から「ASIN -> SKU」のローカル辞書を作る（同一ASINがあれば既存SKUを流用）
   * @returns {Map<string,string>}
   */
  _buildAsinToSkuLocalMap_() {
    const asinToSkuLocal = new Map();
    const sourceRows = Array.isArray(this.allData) ? this.allData : this.data;
    for (const row of sourceRows) {
      const sku = String(row.get("SKU") || '').trim();
      const asin = String(row.get("ASIN") || '').trim();
      if (asin && sku && !asinToSkuLocal.has(asin)) {
        asinToSkuLocal.set(asin, sku);
      }
    }
    return asinToSkuLocal;
  }

  /**
   * SKUが空の行だけを対象に集める（ASIN有無は問わない）
   * @param {BaseRow[]|null} targetRows
   * @returns {{targets: Array<{row: any, rowNum: number, asin: string}>}}
   */
  _collectMissingSkuTargets_(targetRows) {
    const targets = []; // { row, rowNum, asin }
    const rowsToProcess = Array.isArray(targetRows) ? targetRows : this.data;
    for (const row of rowsToProcess) {
      const rowNum = row.rowNumber;
      const sku = String(row.get("SKU") || '').trim();
      const asin = String(row.get("ASIN") || '').trim();
      if (!sku) {
        targets.push({ row, rowNum, asin });
      }
    }
    return { targets };
  }

  writePlanNameToRows(instructionURL) {
    const dateStr = this._formatDateMMDD(new Date());

    return this.writeColumnByFunc("プラン別名", (row) => {
      const deliveryCategory = row.get("納品分類") || '';
      const planNameValue = `${dateStr}${deliveryCategory}`;

      if (instructionURL) {
        return { type: 'formula', value: `=HYPERLINK("${instructionURL}", "${planNameValue}")` };
      }
      return planNameValue;
    });
  }

}
