/* exported updateStatusEstimateFromInboundPlans */

/**
 * 仕入管理シートの「ステータス推測値=納品中」行について、
 * 納品プラン列の値（shipmentId or inboundPlanId）から
 * 該当行のSKUに一致するitemのみの QuantityShipped / QuantityReceived で判定し、
 * ステータス推測値を更新する。
 *
 * ルール:
 * - QuantityReceived >= QuantityShipped -> 在庫あり
 * - 0 < QuantityReceived < QuantityShipped -> 納品中
 * - それ以外は納品中（据え置き）
 */
function updateStatusEstimateFromInboundPlans() {
  const config = getEnvConfig();
  const accessToken = getAuthToken();
  const sheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  const creator = new InboundPlanCreator(accessToken);

  // 対象: ステータス推測値が「納品中」
  sheet.filter('ステータス推測値', ['納品中']);

  const planCol = sheet._getColumnIndexByName('納品プラン') + 1;
  const estimateCol = 101; // CW列（1-indexed）

  const itemsCache = new Map(); // id.value -> items[]
  let updated = 0;
  let skipped = 0;

  for (const row of sheet.data) {
    const rowNum = row && row.rowNumber ? row.rowNumber : null;
    if (!rowNum) continue;

    const sku = String(row.get('SKU') || '').trim();
    if (!sku) {
      console.warn(`[推測ステータス] SKUが空のためスキップ: row=${rowNum}`);
      skipped++;
      continue;
    }

    const r = sheet.sheet.getRange(rowNum, planCol);
    const id = _extractPlanIdentifierFromCell_(r);
    if (!id.value) {
      console.warn(`[推測ステータス] 納品プラン列が空のためスキップ: row=${rowNum}`);
      skipped++;
      continue;
    }

    // shipmentId/inboundPlanId ごとに items をキャッシュ
    let items = itemsCache.get(id.value);
    if (!items) {
      try {
        if (id.type === 'shipmentId') {
          items = creator.getShipmentItems(id.value);
        } else {
          items = _getAllItemsForPlan_(creator, id.value);
        }
        itemsCache.set(id.value, items);
      } catch (e) {
        console.warn(`[推測ステータス] items取得に失敗: ${id.type}=${id.value}, row=${rowNum}, error=${String(e && e.message || e)}`);
        skipped++;
        continue;
      }
    }

    // 該当行のSKUに一致するitemだけで集計
    const totals = _sumQuantitiesForSku_(items, sku);

    let estimate = '納品中';
    if (totals.shipped > 0 && totals.received >= totals.shipped) {
      estimate = '在庫あり';
    } else if (totals.shipped > 0 && totals.received > 0 && totals.received < totals.shipped) {
      estimate = '納品中';
    }

    sheet.writeCell(rowNum, estimateCol, estimate);
    console.log(`[推測ステータス] row=${rowNum} sku=${sku} ${id.type}=${id.value} shipped=${totals.shipped} received=${totals.received} matched=${totals.matchedCount}/${(items || []).length} -> ${estimate}`);
    updated++;
  }

  console.log(`[推測ステータス] 完了: updated=${updated}, skipped=${skipped}, cached=${itemsCache.size}`);
}

/**
 * inboundPlanId 配下の全shipmentのitemsを結合して返す
 */
function _getAllItemsForPlan_(creator, inboundPlanId) {
  const shipments = creator.listShipments(inboundPlanId);
  const shipmentIds = (shipments || []).map(s => s && s.shipmentId ? String(s.shipmentId) : '').filter(Boolean);
  if (shipmentIds.length === 0) {
    console.warn(`[推測ステータス] shipmentsなし: inboundPlanId=${inboundPlanId}`);
    return [];
  }
  let allItems = [];
  for (const sid of shipmentIds) {
    const items = creator.getShipmentItems(sid);
    allItems = allItems.concat(items || []);
  }
  return allItems;
}

/**
 * items配列からSKUに一致するもののみ QuantityShipped / QuantityReceived を集計する。
 * APIバージョンによってフィールド名が異なるため複数候補を試す。
 */
function _sumQuantitiesForSku_(items, sku) {
  let shipped = 0;
  let received = 0;
  let matchedCount = 0;

  for (const it of (items || [])) {
    if (!it) continue;
    const itemSku = String(
      it.msku ?? it.sellerSku ?? it.SellerSKU ?? it.seller_sku ?? it.merchantSku ?? ''
    ).trim();
    if (itemSku !== sku) continue;

    matchedCount++;
    const qS = Number((it.quantityShipped ?? it.QuantityShipped ?? it.quantity_shipped) || 0);
    const qR = Number((it.quantityReceived ?? it.QuantityReceived ?? it.quantity_received) || 0);
    console.log(`[推測ステータス][item] sku=${sku} shipped=${qS} received=${qR} raw=${JSON.stringify(it)}`);
    if (qS) shipped += qS;
    if (qR) received += qR;
  }

  return { shipped, received, matchedCount };
}

/**
 * 納品プラン列のセルから識別子を抽出する。
 * - 表示テキストが FBA で始まる場合 → shipmentId
 * - HYPERLINK の wf= パラメータがある場合 → inboundPlanId
 * - それ以外の表示テキスト → inboundPlanId として扱う
 * @returns {{type: 'shipmentId'|'inboundPlanId', value: string}}
 */
function _extractPlanIdentifierFromCell_(range) {
  const display = String(range.getDisplayValue() || '').trim();
  const formula = String(range.getFormula() || '').trim();

  // HYPERLINK から inboundPlanId（wf=）を抽出
  if (formula) {
    const m = formula.match(/HYPERLINK\("([^"]+)"/i);
    if (m) {
      const url = String(m[1] || '');
      const wf = url.match(/[?&]wf=([^&#"]+)/i);
      if (wf && wf[1]) {
        const planId = (() => { try { return decodeURIComponent(wf[1]); } catch (e) { return String(wf[1]); } })();
        return { type: 'inboundPlanId', value: planId };
      }
    }
  }

  // 表示テキストから判定
  if (display) {
    if (/^FBA[0-9A-Z]+$/i.test(display)) {
      return { type: 'shipmentId', value: display };
    }
    return { type: 'inboundPlanId', value: display };
  }

  return { type: 'inboundPlanId', value: '' };
}

