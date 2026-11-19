/**
 * useTasks - task list state: filters, pagination, loading, errors.
 * Mirrors useDocuments so both pages behave identically.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { listTasks } from '../services/tasks';
import { getErrorMessage } from '../services/api';

export const DEFAULT_TASK_FILTERS = {
  search: '',
  priority: '',
  status: '',
  sortByDue: '',
  page: 1,
  pageSize: 20,
};

export default function useTasks(initialFilters = {}) {
  const [filters, setFilters] = useState({ ...DEFAULT_TASK_FILTERS, ...initialFilters });
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 20, pages: 1, counts: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Only the most recent request may write state (avoids a slow older
  // response overwriting a newer filtered result - see useDocuments).
  const requestSeq = useRef(0);

  const load = useCallback(async (currentFilters) => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError('');
    try {
      const result = await listTasks({
        search: currentFilters.search,
        priority: currentFilters.priority,
        status: currentFilters.status,
        sort_by_due: currentFilters.sortByDue,
        page: currentFilters.page,
        page_size: currentFilters.pageSize,
      });
      if (seq !== requestSeq.current) return;
      setData(result);
    } catch (requestError) {
      if (seq !== requestSeq.current) return;
      setError(getErrorMessage(requestError));
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(filters);
  }, [filters, load]);

  const updateFilters = useCallback((patch, { keepPage = false } = {}) => {
    setFilters((previous) => ({
      ...previous,
      ...patch,
      page: keepPage ? previous.page : 1,
    }));
  }, []);

  const goToPage = useCallback((page) => {
    setFilters((previous) => ({ ...previous, page }));
  }, []);

  const refresh = useCallback(() => {
    load(filters);
  }, [filters, load]);

  return { filters, setFilters, updateFilters, goToPage, refresh, ...data, loading, error };
}
