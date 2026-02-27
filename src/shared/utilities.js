/* exported getEnvConfig, SettingSheet, getAuthToken, getConfigSettingAndToken, DEFAULT_MARKETPLACE_ID, SHIP_FROM_ADDRESS */

const DEFAULT_MARKETPLACE_ID = 'A1VC38T7YXB528';

const SHIP_FROM_ADDRESS = {
  name: '和田篤',
  companyName: '',
  addressLine1: '久喜本847-14',
  addressLine2: '',
  city: '久喜市',
  stateOrProvinceCode: '埼玉県',
  postalCode: '3460031',
  countryCode: 'JP',
  phoneNumber: '05035540337',
  email: ''
};

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
    HOME_SHIPMENT_SHEET_NAME: getEnv('HOME_SHIPMENT_SHEET_NAME', '自宅発送'),
    WORK_RECORD_SHEET_NAME: getEnv('WORK_RECORD_SHEET_NAME', '作業記録'),
    INSPECTION_MASTER_SHEET_ID: getEnv('INSPECTION_MASTER_SHEET_ID', '1xH_-D8XbdP2kdx5U7cWmYwiOHBcLoO621h--sEnAvL0'),
    INSPECTION_MASTER_SHEET_GID: getEnv('INSPECTION_MASTER_SHEET_GID', '414729247'),
    INSPECTION_TEMPLATE_SHEET_ID: getEnv('INSPECTION_TEMPLATE_SHEET_ID', '1qd3raNESIc35YvzPoBBwEKEFySDLw0-XZL9bNAcqcus'),
    INSPECTION_TEMPLATE_SHEET_GID: getEnv('INSPECTION_TEMPLATE_SHEET_GID', '1099050777'),
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

