/**
 * Authentication API calls.
 * Wraps POST /api/auth/register, POST /api/auth/login and GET /api/auth/me.
 */
import api, { setToken, clearToken } from './api';

/** Register a new account and store the returned token. */
export async function register(payload) {
  const { data } = await api.post('/auth/register', payload);
  setToken(data.access_token);
  return data.user;
}

/** Sign in with email + password and store the returned token. */
export async function login(credentials) {
  const { data } = await api.post('/auth/login', credentials);
  setToken(data.access_token);
  return data.user;
}

/** Fetch the profile behind the stored token (used to restore a session). */
export async function fetchCurrentUser() {
  const { data } = await api.get('/auth/me');
  return data;
}

/** Forget the session locally. */
export function logout() {
  clearToken();
}
