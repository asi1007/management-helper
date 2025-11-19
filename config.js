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


