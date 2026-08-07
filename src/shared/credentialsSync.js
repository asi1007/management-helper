/* exported syncSpApiCredentials, getSpApiCredentialFingerprints */

const SP_API_CREDENTIAL_KEYS = ['API_KEY', 'API_SECRET', 'REFRESH_TOKEN'];

function syncSpApiCredentials(credentials) {
  const updates = {};
  SP_API_CREDENTIAL_KEYS.forEach((key) => {
    const value = credentials[key];
    if (typeof value === 'string' && value.length > 0) {
      updates[key] = value;
    }
  });
  if (Object.keys(updates).length === 0) {
    throw new Error('同期対象の認証情報が空です');
  }
  PropertiesService.getScriptProperties().setProperties(updates, false);
  return getSpApiCredentialFingerprints();
}

function getSpApiCredentialFingerprints() {
  const properties = PropertiesService.getScriptProperties();
  const fingerprints = {};
  SP_API_CREDENTIAL_KEYS.forEach((key) => {
    fingerprints[key] = fingerprintOfSecret_(properties.getProperty(key));
  });
  return fingerprints;
}

function fingerprintOfSecret_(value) {
  if (!value) {
    return 'MISSING';
  }
  const digest = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, value, Utilities.Charset.UTF_8);
  return digest
    .slice(0, 4)
    .map((byte) => ('0' + (byte & 0xff).toString(16)).slice(-2))
    .join('');
}
