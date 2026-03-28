/* exported getEnvConfig, getAuthToken, DEFAULT_MARKETPLACE_ID, SHIP_FROM_ADDRESS */

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
    INSPECTION_TEMPLATE_SHEET_ID: getEnv('INSPECTION_TEMPLATE_SHEET_ID', '1U5Bf9BcZBl41GKZ_qcyxtPUEIz11d49nkgJRv6kDi4w'),
    INSPECTION_TEMPLATE_SHEET_GID: getEnv('INSPECTION_TEMPLATE_SHEET_GID', '1711200534'),
    API_KEY: getEnv('API_KEY', 'YOUR_API_KEY_HERE'),
    API_SECRET: getEnv('API_SECRET', 'YOUR_API_SECRET_HERE'),
    REFRESH_TOKEN: getEnv('REFRESH_TOKEN', 'YOUR_REFRESH_TOKEN_HERE'),
    KEEPA_API_KEY: getEnv('KEEPA_API_KEY', 'YOUR_KEEPA_API_KEY_HERE')
  };
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


