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







