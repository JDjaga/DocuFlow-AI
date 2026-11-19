/**
 * useDashboard - loads KPI statistics + chart data from FastAPI.
 *
 * Returns { stats, analytics, loading, error, reload }.
 * `reload()` is called after analyzing a document or completing a task so
 * the numbers refresh without a full page reload.
 */
import { useCallback, useEffect, useState } from 'react';
import { fetchAnalytics, fetchStats } from '../services/dashboard';
import { getErrorMessage } from '../services/api';

export default function useDashboard() {
  const [stats, setStats] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      // Both requests are independent, so they run in parallel.
      const [statsData, analyticsData] = await Promise.all([fetchStats(), fetchAnalytics()]);
      setStats(statsData);
      setAnalytics(analyticsData);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { stats, analytics, loading, error, reload: load };
}
