/** Health API calls used by the API Health page. */
import api from './api';

export async function fetchHealth() {
  const { data } = await api.get('/health');
  return data;
}

export async function fetchAiHealth() {
  const { data } = await api.get('/health/ai');
  return data;
}
