/* exported getEnvConfig, SettingSheet, getAuthToken, getConfigSettingAndToken */

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

  getMultiple(names) {
    const result = {};
    for (const name of names) {
      result[name] = this.get(name);
    }
    return result;
  }

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

function getConfigSettingAndToken() {
  const config = getEnvConfig();
  const setting = new SettingSheet();
  const accessToken = getAuthToken();
  return { config, setting, accessToken };
}

