/**
 * TaskFilters - status tabs (with live counts from the backend),
 * search, priority filter, due-date sort and the list/board view toggle.
 */
import { LayoutGrid, List, Search } from 'lucide-react';
import { PRIORITIES, TASK_STATUSES } from '../../utils/constants';

export default function TaskFilters({ filters, counts, total, onChange, view, onViewChange }) {
  const tabs = [{ value: '', label: 'All' }, ...TASK_STATUSES];

  return (
    <div className="border-b border-slate-100">
      {/* Status tabs */}
      <div className="flex gap-1 overflow-x-auto px-5 pt-4">
        {tabs.map((tab) => {
          const active = filters.status === tab.value;
          const count = tab.value === '' ? total : (counts?.[tab.value] ?? 0);

          return (
            <button
              key={tab.value}
              type="button"
              onClick={() => onChange({ status: tab.value })}
              className={`relative whitespace-nowrap rounded-t-lg px-3.5 py-2 text-sm font-medium transition ${
                active ? 'text-indigo-700' : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              {tab.label}
              <span
                className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs ${
                  active ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-500'
                }`}
              >
                {count}
              </span>
              {active && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-indigo-600" />}
            </button>
          );
        })}
      </div>

      {/* Controls */}
      <div className="flex flex-col gap-3 px-5 py-4 lg:flex-row lg:items-center">
        <div className="relative w-full lg:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            className="input !py-2 !pl-9"
            placeholder="Search tasks…"
            value={filters.search}
            onChange={(event) => onChange({ search: event.target.value })}
            aria-label="Search tasks"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
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
            value={filters.sortByDue}
            onChange={(event) => onChange({ sortByDue: event.target.value })}
            aria-label="Sort by due date"
          >
            <option value="">Newest first</option>
            <option value="asc">Due date (soonest)</option>
            <option value="desc">Due date (latest)</option>
          </select>
        </div>

        {/* List / board toggle */}
        <div className="flex rounded-lg border border-slate-200 p-0.5 lg:ml-auto">
          <button
            type="button"
            onClick={() => onViewChange('list')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition ${
              view === 'list' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <List className="h-3.5 w-3.5" /> List
          </button>
          <button
            type="button"
            onClick={() => onViewChange('board')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition ${
              view === 'board' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <LayoutGrid className="h-3.5 w-3.5" /> Board
          </button>
        </div>
      </div>
    </div>
  );
}
