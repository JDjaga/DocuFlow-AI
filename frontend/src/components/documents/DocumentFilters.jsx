/**
 * DocumentFilters - search box + dropdowns that drive server side queries.
 * Every change resets to page 1 (handled by the useDocuments hook).
 */
import SearchInput from '../common/SearchInput';
import Badge from '../common/Badge';
import { PRIORITIES, PROCESSING_STATUSES } from '../../utils/constants';

export default function DocumentFilters({ filters, categories, onChange, onClear, total }) {
  const hasFilters =
    filters.search || filters.category || filters.priority || filters.status || filters.sort !== 'newest';

  return (
    <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 lg:flex-row lg:items-center">
      <SearchInput
        value={filters.search}
        onSearch={(value) => onChange({ search: value })}
        placeholder="Search by document name…"
      />

      <div className="flex flex-wrap items-center gap-2.5">
        <select
          className="input !w-auto !py-2"
          value={filters.category}
          onChange={(event) => onChange({ category: event.target.value })}
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {categories.map((category) => (
            <option key={category} value={category}>{category}</option>
          ))}
        </select>

        <select
          className="input !w-auto !py-2"
          value={filters.priority}
          onChange={(event) => onChange({ priority: event.target.value })}
          aria-label="Filter by priority"
        >
          <option value="">All priorities</option>
          {PRIORITIES.map((priority) => (
            <option key={priority} value={priority}>{priority}</option>
          ))}
        </select>

        <select
          className="input !w-auto !py-2"
          value={filters.status}
          onChange={(event) => onChange({ status: event.target.value })}
          aria-label="Filter by processing status"
        >
          <option value="">All statuses</option>
          {PROCESSING_STATUSES.map((status) => (
            <option key={status.value} value={status.value}>{status.label}</option>
          ))}
        </select>

        <select
          className="input !w-auto !py-2"
          value={filters.sort}
          onChange={(event) => onChange({ sort: event.target.value })}
          aria-label="Sort documents"
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="title">Name A–Z</option>
          <option value="priority">Priority</option>
        </select>

        {hasFilters && (
          <button type="button" className="btn-ghost !py-2 text-xs" onClick={onClear}>
            Clear filters
          </button>
        )}
      </div>

      <div className="lg:ml-auto">
        <Badge label={`${total} document${total === 1 ? '' : 's'}`} className="border-slate-200 bg-slate-100 text-slate-600" />
      </div>
    </div>
  );
}
