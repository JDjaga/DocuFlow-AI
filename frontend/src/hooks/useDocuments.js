/**
 * useDocuments - document list state: filters, pagination, loading, errors.
 *
 * The backend does the heavy work (search, filter, sort, paginate), so this
 * hook simply keeps the query parameters in sync and refetches when they
 * change. Keeping it here means the Documents page only deals with UI.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { listDocuments } from '../services/documents';
import { getErrorMessage } from '../services/api';

export const DEFAULT_FILTERS = {
  search: '',
  category: '',
  priority: '',
  status: '',
  sort: 'newest',
  page: 1,
  pageSize: 10,
};

export default function useDocuments(initialFilters = {}) {
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS, ...initialFilters });
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 10, pages: 1, categories: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Guards against out-of-order responses: when filters change quickly two
  // requests can be in flight, and only the most recent one may update state.
  const requestSeq = useRef(0);

  const load = useCallback(async (currentFilters) => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError('');
    try {
      const result = await listDocuments({
        search: currentFilters.search,
        category: currentFilters.category,
        priority: currentFilters.priority,
        status: currentFilters.status,
        sort: currentFilters.sort,
        page: currentFilters.page,
        page_size: currentFilters.pageSize,
      });
      if (seq !== requestSeq.current) return; // a newer request already started
      setData(result);
    } catch (requestError) {
      if (seq !== requestSeq.current) return;
      setError(getErrorMessage(requestError));
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, []);

  // Fetch whenever the filters change (including the first render).
  useEffect(() => {
    load(filters);
  }, [filters, load]);

  /** Patch some filter values; resets to page 1 unless a page is given. */
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
