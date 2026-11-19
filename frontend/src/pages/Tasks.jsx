/**
 * Tasks page - full CRUD over workflow tasks with two views.
 *
 *   - List view  (default): paginated table with inline status actions
 *   - Board view: three columns (Pending / In Review / Completed) with
 *     arrow buttons that call the same PUT /api/tasks/{id}
 *
 * Everything is backed by the API: status counts come from the backend,
 * so the tabs always reflect the real data (not numbers typed here).
 */
import { useMemo, useState } from 'react';
import { Plus, RefreshCw, ListChecks } from 'lucide-react';
import toast from 'react-hot-toast';
import PageHeader from '../components/common/PageHeader';
import ConfirmDialog from '../components/common/ConfirmDialog';
import TaskFilters from '../components/tasks/TaskFilters';
import TaskTable from '../components/tasks/TaskTable';
import KanbanBoard from '../components/tasks/KanbanBoard';
import TaskModal from '../components/tasks/TaskModal';
import useTasks from '../hooks/useTasks';
import { deleteTask, updateTask } from '../services/tasks';
import { getErrorMessage } from '../services/api';

export default function Tasks() {
  const {
    filters,
    updateFilters,
    goToPage,
    refresh,
    items,
    total,
    page,
    pages,
    page_size: pageSize,
    counts,
    loading,
    error,
  } = useTasks();

  const [view, setView] = useState('list');
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const hasActiveFilters = useMemo(
    () => Boolean(filters.search || filters.priority || filters.status || filters.sortByDue),
    [filters]
  );

  function clearFilters() {
    updateFilters({ search: '', priority: '', status: '', sortByDue: '' });
  }

  /** Single status transition used by both views. */
  async function handleStatusChange(task, nextStatus) {
    try {
      await updateTask(task.id, { status: nextStatus });
      toast.success(`Task moved to ${nextStatus.replace('_', ' ')}.`);
      refresh();
    } catch (requestError) {
      toast.error(getErrorMessage(requestError));
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteTask(deleteTarget.id);
      toast.success('Task deleted.');
      setDeleteTarget(null);
      refresh();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Workflow Tasks"
        description="Track the decisions extracted from your documents - or add tasks manually."
        actions={
          <>
            <button type="button" className="btn-secondary" onClick={refresh} title="Refresh list">
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
            <button type="button" className="btn-primary" onClick={() => setEditTarget(null) || setModalOpen(true)}>
              <Plus className="h-4 w-4" /> New task
            </button>
          </>
        }
      />

      <div className="card overflow-hidden">
        <TaskFilters
          filters={filters}
          counts={counts}
          total={total}
          onChange={(patch) => updateFilters(patch)}
          view={view}
          onViewChange={setView}
        />

        {error && (
          <div className="border-b border-slate-100 bg-rose-50 px-5 py-3 text-sm text-rose-700">{error}</div>
        )}

        {view === 'list' ? (
          <TaskTable
            items={items}
            loading={loading}
            page={page}
            pages={pages}
            total={total}
            pageSize={pageSize}
            onPageChange={goToPage}
            onEdit={(task) => setEditTarget(task)}
            onDelete={(task) => setDeleteTarget(task)}
            onStatusChange={handleStatusChange}
            hasActiveFilters={hasActiveFilters}
            onClearFilters={clearFilters}
          />
        ) : (
          <div className="p-5">
            <KanbanBoard
              tasks={items}
              loading={loading}
              onStatusChange={handleStatusChange}
              onEdit={(task) => setEditTarget(task)}
              onDelete={(task) => setDeleteTarget(task)}
            />
            {!loading && total > pageSize && (
              <p className="mt-4 text-center text-xs text-slate-400">
                Showing {items.length} of {total} tasks - use the list view and pagination to see the rest.
              </p>
            )}
            {!loading && items.length === 0 && hasActiveFilters && (
              <div className="mt-4 text-center">
                <button type="button" className="btn-secondary" onClick={clearFilters}>
                  Clear filters
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create / edit modal */}
      <TaskModal
        open={modalOpen || Boolean(editTarget)}
        task={editTarget}
        onClose={() => {
          setModalOpen(false);
          setEditTarget(null);
        }}
        onSaved={refresh}
      />

      {/* Delete confirmation */}
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        loading={deleting}
        title="Delete this task?"
        message={`"${deleteTarget?.title}" will be permanently removed from your workflow.`}
        confirmLabel="Delete task"
      />
    </div>
  );
}
