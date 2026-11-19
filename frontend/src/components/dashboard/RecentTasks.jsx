/**
 * RecentTasks - last 5 workflow tasks with their live status.
 */
import { Link } from 'react-router-dom';
import { ArrowRight, ListChecks } from 'lucide-react';
import Badge from '../common/Badge';
import EmptyState from '../common/EmptyState';
import { dueDateTone, formatDate, timeAgo } from '../../utils/formatters';
import { PRIORITY_STYLES, TASK_STATUS_STYLES } from '../../utils/constants';

export default function RecentTasks({ items = [], loading = false }) {
  return (
    <section className="card overflow-hidden">
      <div className="card-header">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Recent Tasks</h2>
          <p className="mt-0.5 text-xs text-slate-500">Work generated from your documents</p>
        </div>
        <Link to="/tasks" className="btn-ghost !px-3 !py-1.5">
          View all <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      {loading && (
        <div className="space-y-3 p-5">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-14 animate-pulse rounded-lg bg-slate-100" />
          ))}
        </div>
      )}

      {!loading && items.length === 0 && (
        <EmptyState
          icon={ListChecks}
          title="No tasks yet"
          description="Convert AI action items into tasks to start tracking decisions."
        />
      )}

      {!loading && items.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {items.map((task) => (
            <li key={task.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5 transition hover:bg-slate-50/60">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-900">{task.title}</p>
                <p className="mt-0.5 truncate text-xs text-slate-500">
                  {task.document_title ? task.document_title : 'Manual task'}
                  {task.assigned_to ? ` · ${task.assigned_to}` : ''}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Badge label={task.priority} className={PRIORITY_STYLES[task.priority]} />
                <Badge label={task.status.replace('_', ' ')} className={TASK_STATUS_STYLES[task.status]} />
              </div>

              <div className="w-28 text-right text-xs text-slate-500">
                {task.due_date ? (
                  <span className={dueDateTone(task.due_date, task.status)}>Due {formatDate(task.due_date)}</span>
                ) : (
                  <span>Created {timeAgo(task.created_at)}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
