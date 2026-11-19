/**
 * CreateTasksModal - turn AI action items into real tasks.
 *
 * The user picks which suggestions to convert (all selected by default).
 * Each one becomes a POST /api/tasks linked to the document. The backend
 * refuses duplicates, so running it twice cannot double your tasks.
 */
import { useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { ListPlus, Loader2 } from 'lucide-react';
import Modal from '../common/Modal';
import Badge from '../common/Badge';
import { createTasksFromActionItems } from '../../services/tasks';
import { getErrorMessage } from '../../services/api';
import { PRIORITY_STYLES } from '../../utils/constants';
import { formatDate } from '../../utils/formatters';

export default function CreateTasksModal({ open, document, onClose, onCreated }) {
  const [selected, setSelected] = useState([]);
  const [creating, setCreating] = useState(false);
  const [progress, setProgress] = useState(null);

  const actionItems = useMemo(() => document?.action_items || [], [document]);

  // Pre-select every suggestion each time the modal opens.
  useEffect(() => {
    if (open) setSelected(actionItems.map((_, index) => index));
  }, [open, actionItems]);

  function toggle(index) {
    setSelected((current) =>
      current.includes(index) ? current.filter((item) => item !== index) : [...current, index]
    );
  }

  async function handleCreate() {
    if (selected.length === 0) return;

    setCreating(true);
    setProgress({ done: 0, total: selected.length });
    try {
      const chosen = selected.map((index) => actionItems[index]);
      const created = await createTasksFromActionItems(document.id, chosen, (done, total) =>
        setProgress({ done, total })
      );
      toast.success(`${created.length} task${created.length > 1 ? 's' : ''} created.`);
      onCreated(created);
      onClose();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setCreating(false);
      setProgress(null);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create tasks from action items"
      description={`${actionItems.length} suggestion(s) extracted from "${document?.title || 'this document'}".`}
      width="max-w-2xl"
    >
      {actionItems.length === 0 ? (
        <p className="text-sm text-slate-500">This document has no suggested action items.</p>
      ) : (
        <>
          <div className="mb-4 flex items-center justify-between text-xs text-slate-500">
            <span>{selected.length} of {actionItems.length} selected</span>
            <div className="flex gap-3">
              <button
                type="button"
                className="font-semibold text-indigo-600 hover:text-indigo-700"
                onClick={() => setSelected(actionItems.map((_, index) => index))}
              >
                Select all
              </button>
              <button
                type="button"
                className="font-semibold text-slate-500 hover:text-slate-700"
                onClick={() => setSelected([])}
              >
                Clear
              </button>
            </div>
          </div>

          <ul className="max-h-[45vh] space-y-2 overflow-y-auto pr-1">
            {actionItems.map((item, index) => {
              const checked = selected.includes(index);
              return (
                <li key={`${item.title}-${index}`}>
                  <label
                    className={`flex cursor-pointer gap-3 rounded-xl border px-4 py-3 transition ${
                      checked ? 'border-indigo-200 bg-indigo-50/60' : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 shrink-0 accent-indigo-600"
                      checked={checked}
                      onChange={() => toggle(index)}
                      disabled={creating}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-sm font-medium text-slate-900">{item.title}</span>
                        <Badge
                          label={item.priority}
                          className={PRIORITY_STYLES[item.priority] || 'border-slate-200 bg-slate-100 text-slate-600'}
                        />
                      </span>
                      {item.description && (
                        <span className="mt-1 block text-xs leading-relaxed text-slate-600">
                          {item.description}
                        </span>
                      )}
                      <span className="mt-1 block text-xs text-slate-400">
                        {item.due_date ? `Due ${formatDate(item.due_date)}` : 'No due date'}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>

          <div className="mt-5 flex items-center justify-between gap-3">
            <p className="text-xs text-slate-400">
              {progress ? `Creating ${progress.done}/${progress.total}…` : 'Duplicates are rejected by the backend.'}
            </p>
            <div className="flex gap-3">
              <button type="button" className="btn-secondary" onClick={onClose} disabled={creating}>
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={handleCreate}
                disabled={creating || selected.length === 0}
              >
                {creating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Creating…
                  </>
                ) : (
                  <>
                    <ListPlus className="h-4 w-4" /> Create {selected.length} task{selected.length === 1 ? '' : 's'}
                  </>
                )}
              </button>
            </div>
          </div>
        </>
      )}
    </Modal>
  );
}
