/**
 * Central Axios setup - the ONLY place in the frontend that knows the backend URL.
 *
 * WHAT THIS FILE DOES
 *   1. creates two axios clients: one for JSON, one for file uploads
 *   2. attaches `Authorization: Bearer <token>` to every request
 *   3. turns backend errors into a readable message (getErrorMessage)
 *   4. logs the user out automatically when the token expires (401)
 *
 * WHY IT EXISTS
 *   Components never build URLs or manage headers themselves. They import
 *   a service (services/documents.js) which uses this client.
 *
 * SECURITY NOTE
 *   The JWT is stored in localStorage for simplicity. That means any
 *   JavaScript running on the same page (for example a malicious browser
 *   extension) could read it. An httpOnly cookie would be safer, but it
 *   needs extra CSRF protection and is harder to explain - so the trade-off
 *   is documented in documentation/02_code_concepts_explained.md.
 */
import axios from 'axios';
import toast from 'react-hot-toast';

// Empty in development -> the Vite proxy forwards /api to port 8001.
const BASE_ORIGIN = import.meta.env.VITE_API_URL || '';
export const API_BASE_URL = `${BASE_ORIGIN}/api`;

export const TOKEN_KEY = 'docuflow_token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

// Analysis can legitimately take up to the backend AI timeout (30s) plus
// the upload, so the client waits a little longer than that.
const TIMEOUT_MS = 120000;

/** JSON client - every regular API call. */
export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
});

/** Upload client - no default Content-Type so the browser can set the
 *  multipart boundary automatically when sending FormData. */
export const uploadApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: TIMEOUT_MS,
});

function attachInterceptors(client) {
  // --- request: add the token -----------------------------------------
  client.interceptors.request.use((config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  // --- response: global error handling --------------------------------
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      const status = error.response?.status;

      // Expired / invalid token: drop it and send the user to the login page.
      if (status === 401 && getToken()) {
        clearToken();
        if (!window.location.pathname.startsWith('/login')) {
          toast.error('Your session expired. Please sign in again.');
          window.location.assign('/login');
        }
      }

      // Network failures never reach a response object.
      if (!error.response) {
        error.friendlyMessage = 'Cannot reach the server. Is the backend running on port 8001?';
      }

      return Promise.reject(error);
    }
  );
}

attachInterceptors(api);
attachInterceptors(uploadApi);

/** Extract a readable message from any axios error. */
export function getErrorMessage(error) {
  if (error?.friendlyMessage) return error.friendlyMessage;

  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || String(item)).join(', ');

  if (error?.code === 'ECONNABORTED') return 'The request took too long. Please try again.';
  return error?.message || 'Something went wrong. Please try again.';
}

export default api;
