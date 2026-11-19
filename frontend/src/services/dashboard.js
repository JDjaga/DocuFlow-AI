/** Dashboard API calls (KPI statistics and chart data). */
import api from './api';

export async function fetchStats() {
  const { data } = await api.get('/dashboard/stats');
  return data;
}

export async function fetchAnalytics() {
  const { data } = await api.get('/dashboard/analytics');
  return data;
}
