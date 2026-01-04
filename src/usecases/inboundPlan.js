function createInboundPlanForRows(sheet, accessToken) {
  const aggregatedItems = sheet.aggregateItems();
  const items = Object.values(aggregatedItems);
  
  if (items.length === 0) {
    throw new Error('納品プランを作成できる有効なSKUがありません');
  }

  const planCreator = new InboundPlanCreator(accessToken);
  const planResult = planCreator.createPlan(items);
  
  sheet.writePlanResult(planResult);
  return planResult;
}

function createInboundPlanFromActiveRows() {
  const config = getEnvConfig();
  const accessToken = getAuthToken();

  const sheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  sheet.getActiveRowData();
  const result = createInboundPlanForRows(sheet, accessToken);
  console.log(`Inbound plan created: inboundPlanId=${result.inboundPlanId}, operationId=${result.operationId}, link=${result.link}`);
  return result;
}

/**
 * 納品プラン作成後、Placement Options を生成→一覧をフォームで表示し、ユーザー選択で確定する。
 * - 候補概要と選択結果は services.js 側で毎回 console.log される
 */
function createInboundPlanFromActiveRowsWithPlacementSelection() {
  const config = getEnvConfig();
  const accessToken = getAuthToken();

  const sheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  sheet.getActiveRowData();

  const aggregatedItems = sheet.aggregateItems();
  const items = Object.values(aggregatedItems);
  if (items.length === 0) {
    throw new Error('納品プランを作成できる有効なSKUがありません');
  }

  const creator = new InboundPlanCreator(accessToken);
  const planResult = creator.createPlan(items);
  sheet.writePlanResult(planResult);

  // 1.5 プラン作成完了待機（placementOptions生成の前に確実に完了させる）
  creator.waitInboundPlanCreation(planResult.operationId);

  const inboundPlanId = planResult.inboundPlanId;
  const placementOptions = creator.getPlacementOptions(inboundPlanId); // ここで候補概要ログが出る
  _showPlacementOptionsDialog_(inboundPlanId, placementOptions);

  console.log(`Inbound plan created (awaiting placement selection): inboundPlanId=${planResult.inboundPlanId}, operationId=${planResult.operationId}, link=${planResult.link}`);
  return planResult;
}

function _showPlacementOptionsDialog_(inboundPlanId, placementOptions) {
  const optionsJson = JSON.stringify(placementOptions || []);
  const html = HtmlService.createHtmlOutput(`
    <div style="font-family: Arial, sans-serif;">
      <h3>Placement Optionを選択</h3>
      <div style="margin:8px 0;">InboundPlanId: <code>${inboundPlanId}</code></div>
      <div id="list"></div>
      <div style="margin-top:12px;">
        <button onclick="submitChoice()">確定</button>
        <button onclick="google.script.host.close()">キャンセル</button>
      </div>
      <pre id="status" style="margin-top:12px; background:#f6f6f6; padding:8px;"></pre>
    </div>

    <script>
      const inboundPlanId = ${JSON.stringify(inboundPlanId)};
      const options = ${optionsJson};

      const list = document.getElementById('list');
      if (!options.length) {
        list.innerHTML = '<div>有効なPlacement Optionsがありません</div>';
      } else {
        function pickModeLabel(o) {
          try {
            const candidates = [
              o && o.transportationMode,
              o && o.shippingMode,
              o && o.shippingMethod,
              o && o.mode
            ].filter(Boolean);
            if (candidates.length > 0) return String(candidates[0]);
            const key = Object.keys(o || {}).find(k => /mode|transport|shipping|pallet/i.test(k));
            if (key) return String(o[key]);
          } catch (e) {}
          return '';
        }

        list.innerHTML = options.map((o, i) => {
          const id = o.placementOptionId || o.placementOptionID || o.id || '(no placementOptionId)';
          const mode = pickModeLabel(o);
          const modeTag = mode ? \`<span style="display:inline-block;margin-left:8px;padding:2px 6px;border-radius:10px;background:\${/pallet/i.test(mode)?'#ffe3e3':'#e7f3ff'};border:1px solid #ccc;">mode: \${mode}</span>\` : '';
          const summary = JSON.stringify(o, null, 2);
          return \`
            <label style="display:block; border:1px solid #ddd; padding:8px; margin:8px 0;">
              <input type="radio" name="po" value="\${id}" \${i===0?'checked':''}/>
              <div><b>placementOptionId:</b> <code>\${id}</code>\${modeTag}</div>
              <details style="margin-top:6px;">
                <summary>詳細(JSON)</summary>
                <pre style="white-space:pre-wrap;">\${summary}</pre>
              </details>
            </label>
          \`;
        }).join('');
      }

      function submitChoice() {
        const picked = document.querySelector('input[name="po"]:checked');
        if (!picked) return;

        document.getElementById('status').textContent = '確定中...';
        google.script.run
          .withSuccessHandler((res) => {
            document.getElementById('status').textContent =
              '確定完了\\n' + JSON.stringify(res, null, 2);
          })
          .withFailureHandler((err) => {
            document.getElementById('status').textContent =
              'エラー\\n' + (err && err.message ? err.message : String(err));
          })
          .confirmPlacementOptionFromDialog(inboundPlanId, picked.value);
      }
    </script>
  `).setWidth(820).setHeight(700);

  SpreadsheetApp.getUi().showModalDialog(html, 'Placement Option選択');
}

function confirmPlacementOptionFromDialog(inboundPlanId, placementOptionId) {
  const accessToken = getAuthToken();
  const creator = new InboundPlanCreator(accessToken);
  const shipments = creator.confirmPlacementOption(inboundPlanId, placementOptionId); // ここで選択結果ログが出る
  return {
    inboundPlanId,
    placementOptionId,
    shipmentIds: (shipments || []).map(s => s.shipmentId).filter(Boolean),
  };
}

