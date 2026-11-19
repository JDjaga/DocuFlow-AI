/**
 * TaskTable - list view with inline status actions.
 * Status changes are a single PUT /api/tasks/{id} and update immediately.
 */
import { CheckCheck, CircleDot, ListChecks, Pencil, RotateCcw, Trash2 } from 'lucide-react';
import Badge from '../common/Badge';
import EmptyState from '../common/EmptyState';
import Pagination from '../common/Pagination';
import { SkeletonRow } from '../common/Skeleton';
import { dueDateTone, formatDate, timeAgo } from '../../utils/formatters';
import { PRIORITY_STYLES, TASK_STATUS_STYLES } from '../../utils/constants';

export default function TaskTable({
  items,
  loading,
  page,
  pages,
  total,
  pageSize,
  onPageChange,
  onEdit,
  onDelete,
  onStatusChange,
  hasActiveFilters,
  onClearFilters,
}) {
  if (!loading && items.length === 0) {
    return (
      <div className="px-5 py-4">
        <EmptyState
          icon={ListChecks}
          title={hasActiveFilters ? 'No tasks match your filters' : 'No tasks yet'}
          description={
            hasActiveFilters
              ? 'Try another status tab or clear the filters.'
              : 'Create a task manually or convert AI action items from a document.'
          }
          action={
            hasActiveFilters ? (
              <button type="button" className="btn-secondary" onClick={onClearFilters}>
                Clear filters
              </button>
            ) : null
          }
        />
      </div>
    );
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] border-collapse">
          <thead className="bg-slate-50/70">
            <tr>
              <th className="th">Task</th>
              <th className="th">Document</th>
              <th className="th">Priority</th>
              <th className="th">Status</th>
              <th className="th">Assignee</th>
              <th className="th">Due date</th>
              <th className="th text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 5 }).map((_, index) => <SkeletonRow key={index} columns={7} />)}

            {!loading &&
              items.map((task) => (
                <tr key={task.id} className="border-b border-slate-100 transition last:border-0 hover:bg-slate-50/70">
                  <td className="td max-w-[280px]">
                    <p className="truncate font-medium text-slate-900">{task.title}</p>
                    {task.description && (
                      <p className="mt-0.5 truncate text-xs text-slate-500">{task.description}</p>
                    )}
                  </td>
                  <td className="td">
                    {task.document_title ? (
                      <span className="text-slate-600">{task.document_title}</span>
                    ) : (
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-500">Manual</span>
                    )}
                  </td>
                  <td className="td">
                    <Badge label={task.priority} className={PRIORITY_STYLES[task.priority]} />
                  </td>
                  <td className="td">
                    <Badge label={task.status.replace('_', ' ')} className={TASK_STATUS_STYLES[task.status]} />
                  </td>
                  <td className="td text-slate-600">{task.assigned_to || '—'}</td>
                  <td className="td whitespace-nowrap">
                    <span className={dueDateTone(task.due_date, task.status)}>
                      {task.due_date ? formatDate(task.due_date) : <span className="text-slate-400">No date</span>}
                    </span>
                    {!task.due_date && (
                      <span className="ml-2 text-xs text-slate-400">{timeAgo(task.created_at)}</span>
                    )}
                  </td>
                  <td className="td">
                    <div className="flex items-center justify-end gap-1">
                      {/* Quick status transitions */}
                      {task.status !== 'completed' && (
                        <button
                          type="button"
                          title={task.status === 'pending' ? 'Move to in review' : 'Mark completed'}
                          onClick={() => onStatusChange(task, task.status === 'pending' ? 'in_review' : 'completed')}
                          className="rounded-lg p-2 text-slate-400 transition hover:bg-emerald-50 hover:text-emerald-600"
                        >
                          {task.status === 'pending' ? <CircleDot className="h-4 w-4" /> : <CheckCheck className="h-4 w-4" />}
                        </button>
                      )}
                      {task.status === 'completed' && (
                        <button
                          type="button"
                          title="Reopen task"
                          onClick={() => onStatusChange(task, 'pending')}
                          className="rounded-lg p-2 text-slate-400 transition hover:bg-amber-50 hover:text-amber-600"
                        >
                          <RotateCcw className="h-4 w-4" />
                        </button>
                      )}
                      <button
                        type="button"
                        title="Edit task"
                        onClick={() => onEdit(task)}
                        className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        title="Delete task"
                        onClick={() => onDelete(task)}
                        className="rounded-lg p-2 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <Pagination page={page} pages={pages} total={total} pageSize={pageSize} onPageChange={onPageChange} />
    </>
  );
}
