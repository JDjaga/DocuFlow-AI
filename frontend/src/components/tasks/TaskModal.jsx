/**
 * TaskModal - create a new task or edit an existing one.
 *
 * Fields: title, description, priority, status, assignee, due date.
 * `document_id` is a hidden field: when it is set the task belongs to a
 * document (converted from an AI action item). The backend rejects a
 * document_id that does not belong to the current user.
 *
 * Used by the Tasks page (create/edit) and can be reused anywhere.
 */
import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import Modal from '../common/Modal';
import { createTask, updateTask } from '../../services/tasks';
import { getErrorMessage } from '../../services/api';
import { PRIORITIES, TASK_STATUSES, PRIORITY_STYLES, TASK_STATUS_STYLES } from '../../utils/constants';

const EMPTY_FORM = {
  title: '',
  description: '',
  priority: 'Medium',
  status: 'pending',
  assigned_to: '',
  due_date: '',
};

export default function TaskModal({ open, task, defaultDocumentId = null, onClose, onSaved }) {
  const [values, setValues] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Prefill for edit mode; reset for create mode, each time it opens.
  useEffect(() => {
    if (!open) return;
    if (task) {
      setValues({
        title: task.title || '',
        description: task.description || '',
        priority: task.priority || 'Medium',
        status: task.status || 'pending',
        assigned_to: task.assigned_to || '',
        due_date: task.due_date || '',
      });
    } else {
      setValues(EMPTY_FORM);
    }
    setError('');
  }, [open, task]);

  function handleChange(event) {
    const { name, value } = event.target;
    setValues((previous) => ({ ...previous, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (!values.title.trim()) {
      setError('Task title is required.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      if (task) {
        // Editing: only send the editable fields.
        const updated = await updateTask(task.id, {
          title: values.title.trim(),
          description: values.description.trim(),
          priority: values.priority,
          status: values.status,
          assigned_to: values.assigned_to.trim() || null,
          due_date: values.due_date || null,
          clear_due_date: !values.due_date, // explicit "remove the date"
        });
        toast.success('Task updated.');
        onSaved(updated);
      } else {
        const payload = {
          title: values.title.trim(),
          description: values.description.trim(),
          priority: values.priority,
          status: values.status,
          assigned_to: values.assigned_to.trim() || null,
          due_date: values.due_date || null,
        };
        if (defaultDocumentId) payload.document_id = defaultDocumentId;
        const created = await createTask(payload);
        toast.success('Task created.');
        onSaved(created);
      }
      onClose();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={task ? 'Edit task' : 'Create task'}
      description={
        task
          ? 'Update the details of this workflow task.'
          : 'Add a task manually. It will appear in your workflow board.'
      }
      width="max-w-xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        <div>
          <label className="label" htmlFor="task-title">Title *</label>
          <input
            id="task-title"
            name="title"
            className="input"
            placeholder="e.g. Review the proposal with the client"
            value={values.title}
            onChange={handleChange}
            maxLength={255}
            autoFocus
          />
        </div>

        <div>
          <label className="label" htmlFor="task-description">Description</label>
          <textarea
            id="task-description"
            name="description"
            className="textarea !min-h-[100px]"
            placeholder="Optional context, acceptance criteria or links…"
            value={values.description}
            onChange={handleChange}
            maxLength={2000}
          />
          <p className="mt-1 text-right text-xs text-slate-400">{values.description.length}/2000</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="task-priority">Priority</label>
            <select
              id="task-priority"
              name="priority"
              className="input"
              value={values.priority}
              onChange={handleChange}
            >
              {PRIORITIES.map((priority) => (
                <option key={priority} value={priority}>{priority}</option>
              ))}
            </select>
            <div className="mt-1.5">
              <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${PRIORITY_STYLES[values.priority]}`}>
                {values.priority}
              </span>
            </div>
          </div>

          <div>
            <label className="label" htmlFor="task-status">Status</label>
            <select
              id="task-status"
              name="status"
              className="input"
              value={values.status}
              onChange={handleChange}
            >
              {TASK_STATUSES.map((status) => (
                <option key={status.value} value={status.value}>{status.label}</option>
              ))}
            </select>
            <div className="mt-1.5">
              <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${TASK_STATUS_STYLES[values.status]}`}>
                {values.status.replace('_', ' ')}
              </span>
            </div>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="task-assignee">Assigned to</label>
            <input
              id="task-assignee"
              name="assigned_to"
              className="input"
              placeholder="Leave empty for yourself"
              value={values.assigned_to}
              onChange={handleChange}
              maxLength={120}
            />
          </div>

          <div>
            <label className="label" htmlFor="task-due">Due date</label>
            <input
              id="task-due"
              name="due_date"
              type="date"
              className="input"
              value={values.due_date}
              onChange={handleChange}
            />
          </div>
        </div>

        {defaultDocumentId && !task && (
          <p className="rounded-lg bg-indigo-50 px-3.5 py-2.5 text-xs text-indigo-700">
            This task will be linked to one of your documents.
          </p>
        )}

        <div className="flex justify-end gap-3 pt-1">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? 'Saving…' : task ? 'Save changes' : 'Create task'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
