function decodeJwtPayload(token) {
  try {
    const [, payload] = token.split('.');
    if (!payload) {
      return null;
    }
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const json = atob(normalized);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function isTokenValid(token) {
  if (!token) {
    return false;
  }
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') {
    return false;
  }
  const now = Math.floor(Date.now() / 1000);
  return payload.exp > now;
}

export function clearSession() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
}
