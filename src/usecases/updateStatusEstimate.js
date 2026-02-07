/* exported updateStatusEstimateFromInboundPlans */

/**
 * 仕入管理シートの「ステータス推測値=納品中」行について、
 * 納品プラン列の値（shipmentId or inboundPlanId）から
 * QuantityShipped / QuantityReceived を取得し、ステータス推測値を更新する。
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

  const totalsCache = new Map();
  let updated = 0;
  let skipped = 0;

  for (const row of sheet.data) {
    const rowNum = row && row.rowNumber ? row.rowNumber : null;
    if (!rowNum) continue;

    const r = sheet.sheet.getRange(rowNum, planCol);
    const id = _extractPlanIdentifierFromCell_(r);
    if (!id.value) {
      console.warn(`[推測ステータス] 納品プラン列が空のためスキップ: row=${rowNum}`);
      skipped++;
      continue;
    }

    let totals = totalsCache.get(id.value);
    if (!totals) {
      try {
        if (id.type === 'shipmentId') {
          totals = creator.getShipmentQuantityTotals(id.value);
        } else {
          totals = creator.getPlanQuantityTotals(id.value);
        }
        totalsCache.set(id.value, totals);
      } catch (e) {
        console.warn(`[推測ステータス] 数量取得に失敗: ${id.type}=${id.value}, row=${rowNum}, error=${String(e && e.message || e)}`);
        skipped++;
        continue;
      }
    }

    const shipped = Number((totals && totals.quantityShipped) || 0);
    const received = Number((totals && totals.quantityReceived) || 0);

    let estimate = '納品中';
    if (shipped > 0 && received >= shipped) {
      estimate = '在庫あり';
    } else if (shipped > 0 && received > 0 && received < shipped) {
      estimate = '納品中';
    }

    sheet.writeCell(rowNum, estimateCol, estimate);
    console.log(`[推測ステータス] row=${rowNum} ${id.type}=${id.value} shipped=${shipped} received=${received} -> ${estimate}`);
    updated++;
  }

  console.log(`[推測ステータス] 完了: updated=${updated}, skipped=${skipped}, cached=${totalsCache.size}`);
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

