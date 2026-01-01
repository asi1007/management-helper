/* exported recordWorkStart, recordWorkEnd, recordDefect */

function recordWorkStart() {
  const { config } = getConfigSettingAndToken();
  
  // 自宅発送シートでアクティブな行のデータを取得
  const homeSheet = new HomeShipmentSheet(config.HOME_SHIPMENT_SHEET_NAME);
  const activeData = homeSheet.getActiveRowData();
  
  if (activeData.length === 0) {
    throw new Error('選択された行がありません');
  }
  
  // 作業記録シートに追加
  console.log(`作業記録シート名: ${config.WORK_RECORD_SHEET_NAME}`);
  const workRecordSheet = new WorkRecordSheet(config.WORK_RECORD_SHEET_NAME);
  const timestamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');
  
  for (const row of activeData) {
    const asin = row.get("ASIN");
    const purchaseDate = row.get("購入日");
    
    if (!asin) {
      console.warn(`ASINが空の行をスキップしました`);
      continue;
    }
    
    workRecordSheet.appendRecord(asin, purchaseDate, "開始", timestamp);
  }
  
  console.log(`${activeData.length}件の作業記録（開始）を追加しました`);
}

function recordWorkEnd() {
  const { config } = getConfigSettingAndToken();
  
  // 自宅発送シートでアクティブな行のデータを取得
  const homeSheet = new HomeShipmentSheet(config.HOME_SHIPMENT_SHEET_NAME);
  const activeData = homeSheet.getActiveRowData();
  
  if (activeData.length === 0) {
    throw new Error('選択された行がありません');
  }
  
  // 作業記録シートに追加
  console.log(`作業記録シート名: ${config.WORK_RECORD_SHEET_NAME}`);
  const workRecordSheet = new WorkRecordSheet(config.WORK_RECORD_SHEET_NAME);
  const timestamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');
  
  for (const row of activeData) {
    const asin = row.get("ASIN");
    const purchaseDate = row.get("購入日");
    
    if (!asin) {
      console.warn(`ASINが空の行をスキップしました`);
      continue;
    }
    
    workRecordSheet.appendRecord(asin, purchaseDate, "終了", timestamp);
  }
  
  console.log(`${activeData.length}件の作業記録（終了）を追加しました`);
}

function recordDefect() {
  const config = getEnvConfig();
  
  // 1. 自宅発送シートのS列から不良原因リストを読み込み
  const homeSheet = new HomeShipmentSheet(config.HOME_SHIPMENT_SHEET_NAME);
  const defectReasonList = homeSheet.getDefectReasonList();
  
  if (defectReasonList.length === 0) {
    Browser.msgBox('エラー', '不良原因リストが見つかりません。自宅発送シートのS列に不良原因を入力してください。', Browser.Buttons.OK);
    return;
  }
  
  // 2. 該当行の行番号を取得
  const activeData = homeSheet.getActiveRowData();
  if (activeData.length === 0) {
    Browser.msgBox('エラー', '選択された行がありません。', Browser.Buttons.OK);
    return;
  }
  
  // BaseRow(row) から直接、実シート上の行番号を取得する
  const rowNumbers = activeData.map(row => row.rowNumber).filter(rn => rn !== null && rn !== undefined && rn !== '');
  if (rowNumbers.length === 0) {
    Browser.msgBox('エラー', '選択された行に有効な行番号がありません。', Browser.Buttons.OK);
    return;
  }
  
  // 3. HTMLフォームを表示して不良数、原因、コメントを入力
  const htmlOutput = HtmlService.createHtmlOutput(_getDefectFormHtml(defectReasonList))
    .setWidth(500)
    .setHeight(400);
  
  const ui = SpreadsheetApp.getUi();
  ui.showModalDialog(htmlOutput, '不良品登録');
  
  // フォームの結果はクライアント側からサーバー側の関数を呼び出す必要があるため、
  // フォーム送信時に直接処理するように変更
}

function _getDefectFormHtml(defectReasonList) {
  const reasonOptions = defectReasonList.map((reason, index) => 
    `<option value="${index}">${reason}</option>`
  ).join('');
  
  return `
    <!DOCTYPE html>
    <html>
      <head>
        <base target="_top">
        <style>
          body {
            font-family: Arial, sans-serif;
            padding: 20px;
          }
          .form-group {
            margin-bottom: 15px;
          }
          label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
          }
          input[type="number"], select, textarea {
            width: 100%;
            padding: 8px;
            box-sizing: border-box;
            font-size: 14px;
          }
          textarea {
            height: 80px;
            resize: vertical;
          }
          .button-group {
            margin-top: 20px;
            text-align: right;
          }
          button {
            padding: 10px 20px;
            margin-left: 10px;
            font-size: 14px;
            cursor: pointer;
          }
          .btn-primary {
            background-color: #4285f4;
            color: white;
            border: none;
            border-radius: 4px;
          }
          .btn-secondary {
            background-color: #f1f1f1;
            color: #333;
            border: 1px solid #ccc;
            border-radius: 4px;
          }
          .btn-primary:hover {
            background-color: #357ae8;
          }
          .btn-secondary:hover {
            background-color: #e0e0e0;
          }
        </style>
      </head>
      <body>
        <form id="defectForm">
          <div class="form-group">
            <label for="quantity">不良数 *</label>
            <input type="number" id="quantity" name="quantity" min="1" required>
          </div>
          <div class="form-group">
            <label for="reason">原因 *</label>
            <select id="reason" name="reason" required>
              <option value="">選択してください</option>
              ${reasonOptions}
            </select>
          </div>
          <div class="form-group">
            <label for="comment">コメント（任意）</label>
            <textarea id="comment" name="comment" placeholder="コメントを入力してください"></textarea>
          </div>
          <div class="button-group">
            <button type="button" class="btn-secondary" onclick="google.script.host.close()">キャンセル</button>
            <button type="submit" class="btn-primary">登録</button>
          </div>
        </form>
        <script>
          document.getElementById('defectForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const quantity = parseInt(document.getElementById('quantity').value);
            const reasonIndex = parseInt(document.getElementById('reason').value);
            const comment = document.getElementById('comment').value;
            
            if (isNaN(quantity) || quantity <= 0) {
              alert('有効な不良数を入力してください。');
              return;
            }
            
            if (reasonIndex === '' || isNaN(reasonIndex)) {
              alert('原因を選択してください。');
              return;
            }
            
            google.script.run
              .withSuccessHandler(function(message) {
                alert(message || '不良品登録を完了しました。');
                google.script.host.close();
              })
              .withFailureHandler(function(error) {
                alert('エラーが発生しました: ' + error.message);
              })
              ._processDefectRecord(quantity, reasonIndex, comment);
          });
        </script>
      </body>
    </html>
  `;
}

function _processDefectRecord(quantity, reasonIndex, comment) {
  const config = getEnvConfig();
  
  // 自宅発送シートのS列から不良原因リストを読み込み
  const homeSheet = new HomeShipmentSheet(config.HOME_SHIPMENT_SHEET_NAME);
  const defectReasonList = homeSheet.getDefectReasonList();
  
  if (reasonIndex < 0 || reasonIndex >= defectReasonList.length) {
    throw new Error('無効な原因が選択されました。');
  }
  
  const selectedReason = defectReasonList[reasonIndex];
  
  // 該当行の行番号を取得
  const activeData = homeSheet.getActiveRowData();
  if (activeData.length === 0) {
    throw new Error('選択された行がありません。');
  }
  
  // BaseRow(row) から直接、実シート上の行番号を取得する
  const rowNumbers = activeData.map(row => row.get("行番号")).filter(rn => rn !== null && rn !== undefined && rn !== '');
  if (rowNumbers.length === 0) {
    throw new Error('選択された行に有効な行番号がありません。');
  }
  
  // 仕入管理シートの購入数を不良数分減らす
  const purchaseSheet = new PurchaseSheet(config.PURCHASE_SHEET_NAME);
  purchaseSheet.filter("行番号", rowNumbers);
  
  if (purchaseSheet.data.length === 0) {
    throw new Error('仕入管理シートに対応する行が見つかりません。');
  }
  
  purchaseSheet.decreasePurchaseQuantity(quantity);
  
  // 作業記録に登録
  const workRecordSheet = new WorkRecordSheet(config.WORK_RECORD_SHEET_NAME);
  const timestamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');
  
  for (const row of activeData) {
    const asin = row.get("ASIN");
    const purchaseDate = row.get("購入日");
    
    if (!asin) {
      console.warn(`ASINが空の行をスキップしました`);
      continue;
    }
    
    // ステータスは「不良」のみを記録し、原因とコメントは別の列に記録
    workRecordSheet.appendRecord(asin, purchaseDate, "不良", timestamp, quantity, selectedReason, comment || null);
  }
  
  console.log(`${activeData.length}件の不良品記録を追加しました`);
  return `不良品登録を完了しました。\n不良数: ${quantity}\n原因: ${selectedReason}`;
}

