/**
 * KanbanBoard - simple three column board view.
 *
 * No drag and drop on purpose (keeps the code easy to understand):
 * move a task with the arrow buttons, which call the same
 * PUT /api/tasks/{id} used by the list view.
 */
import { ArrowLeft, ArrowRight, ListChecks, Pencil, Trash2 } from 'lucide-react';
import Badge from '../common/Badge';
import { dueDateTone, formatDate } from '../../utils/formatters';
import { PRIORITY_STYLES, TASK_STATUS_STYLES } from '../../utils/constants';

const COLUMNS = [
  { value: 'pending', title: 'Pending', empty: 'No pending tasks' },
  { value: 'in_review', title: 'In Review', empty: 'Nothing in review' },
  { value: 'completed', title: 'Completed', empty: 'Nothing completed yet' },
];

export default function KanbanBoard({ tasks, loading, onStatusChange, onEdit, onDelete }) {
  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-3">
        {COLUMNS.map((column) => (
          <div key={column.value} className="card h-64 animate-pulse bg-slate-100" />
        ))}
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="card px-6 py-16">
        <div className="empty-state !py-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
            <ListChecks className="h-7 w-7" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">No tasks in this view</h3>
            <p className="mt-1 text-sm text-slate-500">Change the filters or create a new task.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {COLUMNS.map((column) => {
        const columnTasks = tasks.filter((task) => task.status === column.value);

        return (
          <section key={column.value} className="flex flex-col rounded-2xl border border-slate-200 bg-slate-100/70">
            <header className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-2">
                <span className={`text-sm font-semibold text-slate-800`}>{column.title}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                    TASK_STATUS_STYLES[column.value].split(' ')[0]
                  } ${TASK_STATUS_STYLES[column.value].split(' ')[1]}`}
                >
                  {columnTasks.length}
                </span>
              </div>
            </header>

            <div className="flex-1 space-y-2.5 px-3 pb-3">
              {columnTasks.length === 0 && (
                <p className="rounded-lg border border-dashed border-slate-300 px-3 py-6 text-center text-xs text-slate-400">
                  {column.empty}
                </p>
              )}

              {columnTasks.map((task, index) => {
                const columnIndex = COLUMNS.findIndex((item) => item.value === task.status);
                const canMoveLeft = columnIndex > 0;
                const canMoveRight = columnIndex < COLUMNS.length - 1;

                return (
                  <article
                    key={task.id}
                    className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm transition hover:border-indigo-200"
                    style={{ marginLeft: index % 2 ? 6 : 0 }}
                  >
                    <p className="text-sm font-medium leading-snug text-slate-900">{task.title}</p>
                    {task.document_title && (
                      <p className="mt-1 truncate text-xs text-slate-400">{task.document_title}</p>
                    )}

                    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                      <Badge label={task.priority} className={PRIORITY_STYLES[task.priority]} />
                      {task.due_date && (
                        <span className={`text-xs ${dueDateTone(task.due_date, task.status)}`}>
                          {formatDate(task.due_date)}
                        </span>
                      )}
                    </div>

                    <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2.5">
                      <button
                        type="button"
                        disabled={!canMoveLeft}
                        onClick={() => onStatusChange(task, COLUMNS[columnIndex - 1].value)}
                        className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:opacity-30"
                        title={canMoveLeft ? `Move to ${COLUMNS[columnIndex - 1].title}` : 'Already at the first stage'}
                      >
                        <ArrowLeft className="h-4 w-4" />
                      </button>

                      <div className="flex gap-1">
                        <button
                          type="button"
                          onClick={() => onEdit(task)}
                          className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                          title="Edit task"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => onDelete(task)}
                          className="rounded-md p-1.5 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                          title="Delete task"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>

                      <button
                        type="button"
                        disabled={!canMoveRight}
                        onClick={() => onStatusChange(task, COLUMNS[columnIndex + 1].value)}
                        className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:opacity-30"
                        title={canMoveRight ? `Move to ${COLUMNS[columnIndex + 1].title}` : 'Already completed'}
                      >
                        <ArrowRight className="h-4 w-4" />
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
