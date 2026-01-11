/* exported updateStatusEstimateFromInboundPlans */

/**
 * 仕入管理シートの「ステータス=納品中」行について、
 * 納品プラン(inboundPlanId)から QuantityShipped / QuantityReceived を取得し、
 * 101列目(ステータス推測値)を更新する。
 *
 * ルール:
 * - QuantityReceived == QuantityShipped -> 在庫あり
 * - 0 < QuantityReceived < QuantityShipped -> 納品中
 * - それ以外は納品中（据え置き）
 */
function updateStatusEstimateFromInboundPlans() {
  const config = getEnvConfig();
  const accessToken = getAuthToken();
  const sheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  const creator = new InboundPlanCreator(accessToken);

  // 対象: 元ステータスが「納品中」
  sheet.filter('ステータス', ['納品中']);

  const planCol = sheet._getColumnIndexByName('納品プラン') + 1;
  const estimateCol = 101; // CW列（1-indexed）

  const totalsCache = new Map(); // inboundPlanId -> {quantityShipped, quantityReceived}
  let updated = 0;
  let skipped = 0;

  for (const row of sheet.data) {
    const rowNum = row && row.rowNumber ? row.rowNumber : null;
    if (!rowNum) continue;

    const r = sheet.sheet.getRange(rowNum, planCol);
    const inboundPlanId = _extractInboundPlanIdFromPlanCell_(r);
    if (!inboundPlanId) {
      console.warn(`[推測ステータス] inboundPlanIdを抽出できないためスキップ: row=${rowNum}`);
      skipped++;
      continue;
    }

    let totals = totalsCache.get(inboundPlanId);
    if (!totals) {
      try {
        totals = creator.getPlanQuantityTotals(inboundPlanId);
        totalsCache.set(inboundPlanId, totals);
      } catch (e) {
        console.warn(`[推測ステータス] 数量取得に失敗: inboundPlanId=${inboundPlanId}, row=${rowNum}, error=${String(e && e.message || e)}`);
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
    console.log(`[推測ステータス] row=${rowNum} inboundPlanId=${inboundPlanId} shipped=${shipped} received=${received} -> ${estimate}`);
    updated++;
  }

  console.log(`[推測ステータス] 完了: updated=${updated}, skipped=${skipped}, inboundPlanIds=${totalsCache.size}`);
}

function _extractInboundPlanIdFromPlanCell_(range) {
  const display = String(range.getDisplayValue() || '').trim();
  if (display) {
    // display が inboundPlanId の想定（writePlanResultがinboundPlanIdを表示テキストにするため）
    return display;
  }

  const formula = String(range.getFormula() || '').trim();
  if (!formula) return '';

  // =HYPERLINK("url","text") から url を抜く
  const m = formula.match(/HYPERLINK\(\"([^\"]+)\"/i);
  if (!m) return '';

  const url = String(m[1] || '');
  // createPlanのlinkは ...?wf=${inboundPlanId}
  const wf = url.match(/[?&]wf=([^&#"]+)/i);
  if (wf && wf[1]) {
    try { return decodeURIComponent(wf[1]); } catch (e) { return String(wf[1]); }
  }

  return '';
}

