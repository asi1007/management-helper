/* exported setPackingInfoFromActiveRow_, submitPackingInfoFromDialog_ */

function _parseCartonInput(inputText) {
  const lines = String(inputText || '').split('\n').filter(line => line.trim());
  const cartons = [];

  for (const line of lines) {
    const match = line.match(/^(\d+(?:-\d+)?)\s*[：:]\s*(\d+(?:\.\d+)?)\s*[*×x]\s*(\d+(?:\.\d+)?)\s*[*×x]\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*(?:KG|kg)?$/i);
    if (!match) {
      throw new Error(`解析できない行: "${line}"\n形式: 箱番号：長さ*幅*高さ 重さKG\n例: 1-2：60*40*32 29.1KG`);
    }

    const [, boxRange, lengthCm, widthCm, heightCm, weightKg] = match;
    const dimensions = {
      length: parseFloat(lengthCm),
      width: parseFloat(widthCm),
      height: parseFloat(heightCm)
    };
    const weight = parseFloat(weightKg);

    if (boxRange.includes('-')) {
      const [start, end] = boxRange.split('-').map(Number);
      for (let i = start; i <= end; i++) {
        cartons.push({ boxNumber: i, dimensions, weight });
      }
    } else {
      cartons.push({ boxNumber: parseInt(boxRange, 10), dimensions, weight });
    }
  }

  cartons.sort((a, b) => a.boxNumber - b.boxNumber);
  return cartons;
}

function _cmToInches(cm) {
  return Math.round(cm / 2.54 * 100) / 100;
}

function _kgToLbs(kg) {
  return Math.round(kg * 2.20462 * 100) / 100;
}

function _extractInboundPlanIdFromCell(cellValue) {
  const value = String(cellValue || '');
  const wfMatch = value.match(/wf[a-f0-9-]+/i);
  if (wfMatch) {
    return wfMatch[0];
  }
  if (/^wf[a-f0-9-]+$/i.test(value.trim())) {
    return value.trim();
  }
  throw new Error(`納品プランIDを特定できません: "${value}"`);
}

function setPackingInfoFromActiveRow_() {
  const config = getEnvConfig();
  const sheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  sheet.getActiveRowData();

  if (sheet.data.length === 0) {
    throw new Error('選択された行がありません');
  }

  const row = sheet.data[0];
  const planCellValue = row.get('納品プラン');
  const inboundPlanId = _extractInboundPlanIdFromCell(planCellValue);

  console.log(`[setPackingInfo] inboundPlanId=${inboundPlanId}`);

  _showPackingInfoDialog_(inboundPlanId);
}

function _showPackingInfoDialog_(inboundPlanId) {
  const html = HtmlService.createHtmlOutput(`
    <div style="font-family: Arial, sans-serif; padding: 8px;">
      <h3>荷物情報を入力</h3>
      <div style="margin:8px 0;">InboundPlanId: <code>${inboundPlanId}</code></div>
      <div style="margin:8px 0;">
        <label>
          荷物情報（1行に1パターン）：
          <br>
          <textarea id="cartonInput" rows="10" cols="50" placeholder="1-2：60*40*32　29.1KG&#10;3：30*40*50　25.8KG&#10;4：30*40*50　28.2KG"></textarea>
        </label>
      </div>
      <div style="margin:8px 0; font-size:12px; color:#666;">
        形式: 箱番号：長さ*幅*高さ 重さKG<br>
        箱番号は「1-2」のように範囲指定も可能（同じサイズ・重さの場合）
      </div>
      <div style="margin-top:12px;">
        <button onclick="submitCartonInfo()">送信</button>
        <button onclick="google.script.host.close()">キャンセル</button>
      </div>
      <pre id="status" style="margin-top:12px; background:#f6f6f6; padding:8px;"></pre>
    </div>

    <script>
      const inboundPlanId = ${JSON.stringify(inboundPlanId)};

      function submitCartonInfo() {
        const input = document.getElementById('cartonInput').value;
        if (!input.trim()) {
          document.getElementById('status').textContent = '荷物情報を入力してください';
          return;
        }

        document.getElementById('status').textContent = '送信中...';
        google.script.run
          .withSuccessHandler((res) => {
            document.getElementById('status').textContent =
              '完了\\n' + JSON.stringify(res, null, 2);
          })
          .withFailureHandler((err) => {
            document.getElementById('status').textContent =
              'エラー\\n' + (err && err.message ? err.message : String(err));
          })
          .submitPackingInfoFromDialog(inboundPlanId, input);
      }
    </script>
  `).setWidth(600).setHeight(500);

  SpreadsheetApp.getUi().showModalDialog(html, '荷物情報入力');
}

function submitPackingInfoFromDialog_(inboundPlanId, cartonInputText) {
  const accessToken = getAuthToken();
  const creator = new InboundPlanCreator(accessToken);

  const cartons = _parseCartonInput(cartonInputText);
  console.log(`[setPackingInfo] parsed cartons: ${JSON.stringify(cartons)}`);

  const packingGroupId = creator.getPackingGroupId(inboundPlanId);
  console.log(`[setPackingInfo] packingGroupId=${packingGroupId}`);

  const items = creator.getPackingGroupItems(inboundPlanId, packingGroupId);
  console.log(`[setPackingInfo] items count=${items.length}`);

  const result = creator.setPackingInformation(inboundPlanId, packingGroupId, cartons, items);
  console.log(`[setPackingInfo] result: ${JSON.stringify(result)}`);

  return result;
}
