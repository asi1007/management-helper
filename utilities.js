/* exported getEnvConfig, SettingSheet, getAuthToken, getConfigAndSetting, getConfigSettingAndToken */

/**
 * 環境変数をPropertiesServiceから取得
 * @returns {Object} 環境変数のオブジェクト
 */
function getEnvConfig() {
  const properties = PropertiesService.getScriptProperties();
  const getEnv = (key, defaultValue = null) => {
    const value = properties.getProperty(key);
    return value !== null ? value : defaultValue;
  };

  return {
    SHEET_ID: getEnv('SHEET_ID', 'YOUR_SHEET_ID_HERE'),
    INSTRUCTION_SHEET_NAME: getEnv('INSTRUCTION_SHEET_NAME', 'yiwu指示書'),
    PURCHASE_SHEET_NAME: getEnv('PURCHASE_SHEET_NAME', '仕入管理'),
    API_KEY: getEnv('API_KEY', 'YOUR_API_KEY_HERE'),
    API_SECRET: getEnv('API_SECRET', 'YOUR_API_SECRET_HERE'),
    REFRESH_TOKEN: getEnv('REFRESH_TOKEN', 'YOUR_REFRESH_TOKEN_HERE'),
    KEEPA_API_KEY: getEnv('KEEPA_API_KEY', 'YOUR_KEEPA_API_KEY_HERE')
  };
}

/**
 * 設定シートから設定値を読み込むクラス
 */
class SettingSheet{
  constructor(){
    const config = getEnvConfig();
    this.sheet = SpreadsheetApp.openById(config.SHEET_ID).getSheetByName("設定");
    const sheetData = this.sheet.getRange(1, 1, this.sheet.getLastRow(), 2).getValues();
    this.data = {};
    for (let i = 0; i < sheetData.length; i++) {
      this.data[sheetData[i][0]] = sheetData[i][1];
    }
  }

  get(name){
    const value = this.data[name];
    if (value === undefined || value === null || value === '') {
      throw new Error(`設定 "${name}" が見つかりません`);
    }
    const columnIndex = value - 1;
    if (columnIndex < 0) {
      throw new Error(`設定 "${name}" の列番号が無効です: ${columnIndex}`);
    }
    return columnIndex;
  }

  getOptional(name){
    const value = this.data[name];
    if (value === undefined || value === null || value === '') {
      return null;
    }
    const columnIndex = value - 1;
    if (columnIndex < 0) {
      console.warn(`設定 "${name}" の列番号が無効です: ${columnIndex}`);
      return null;
    }
    return columnIndex;
  }

  /**
   * 複数の設定を一度に取得（必須）
   * @param {Array<string>} names - 設定名の配列
   * @returns {Object} 設定名をキーとした列インデックスのオブジェクト
   */
  getMultiple(names) {
    const result = {};
    for (const name of names) {
      result[name] = this.get(name);
    }
    return result;
  }

  /**
   * 複数の設定を一度に取得（オプション）
   * @param {Array<string>} names - 設定名の配列
   * @returns {Object} 設定名をキーとした列インデックスのオブジェクト（見つからない場合はnull）
   */
  getMultipleOptional(names) {
    const result = {};
    for (const name of names) {
      result[name] = this.getOptional(name);
    }
    return result;
  }

  /**
   * 複数のキー候補から列インデックスを取得（最初に見つかったものを返す）
   * @param {Array<string>} keyCandidates - キーの候補配列
   * @returns {Array<number>} 列インデックスの配列
   */
  getColumnIndices(keyCandidates) {
    const indices = [];
    for (const key of keyCandidates) {
      const idx = this.getOptional(key);
      if (idx !== null) {
        indices.push(idx);
      }
    }
    return indices;
  }
}

/**
 * Amazon SP-APIのアクセストークンを取得
 * @returns {string} アクセストークン
 */
function getAuthToken() {
  const config = getEnvConfig();
  const url = "https://api.amazon.com/auth/o2/token";
  const payload = {
    'grant_type': 'refresh_token',
    'refresh_token': config.REFRESH_TOKEN,
    'client_id': config.API_KEY,
    'client_secret': config.API_SECRET
  };
  const options = {
    method: 'post',
    payload: payload
  };
  const response = UrlFetchApp.fetch(url, options);
  const json = JSON.parse(response.getContentText());
  return json.access_token;
}

/**
 * 環境変数と設定シートを1回の呼び出しで取得
 * @returns {Object} {config: Object, setting: SettingSheet} の形式のオブジェクト
 */
function getConfigAndSetting() {
  const config = getEnvConfig();
  const setting = new SettingSheet();
  return { config, setting };
}

/**
 * 環境変数、設定シート、アクセストークンを1回の呼び出しで取得
 * @returns {Object} {config: Object, setting: SettingSheet, accessToken: string} の形式のオブジェクト
 */
function getConfigSettingAndToken() {
  const config = getEnvConfig();
  const setting = new SettingSheet();
  const accessToken = getAuthToken();
  return { config, setting, accessToken };
}

