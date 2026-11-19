/**
 * EditDocumentModal - edit the fields a user is allowed to change:
 * title, category, priority and their own notes.
 * Saves through PUT /api/documents/{id}.
 */
import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import Modal from '../common/Modal';
import { updateDocument } from '../../services/documents';
import { getErrorMessage } from '../../services/api';
import { DOCUMENT_CATEGORIES, PRIORITIES, PRIORITY_STYLES } from '../../utils/constants';

export default function EditDocumentModal({ open, document, onClose, onSaved }) {
  const [values, setValues] = useState({ title: '', category: '', priority: 'Medium', user_notes: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Prefill whenever a (different) document is opened.
  useEffect(() => {
    if (!document) return;
    setValues({
      title: document.title || '',
      category: document.category || 'General Document',
      priority: document.priority || 'Medium',
      user_notes: document.user_notes || '',
    });
    setError('');
  }, [document]);

  if (!document) return null;

  const categories = DOCUMENT_CATEGORIES.includes(document.category)
    ? DOCUMENT_CATEGORIES
    : [document.category, ...DOCUMENT_CATEGORIES];

  async function handleSubmit(event) {
    event.preventDefault();
    if (!values.title.trim()) {
      setError('Title cannot be empty.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      const updated = await updateDocument(document.id, {
        title: values.title.trim(),
        category: values.category,
        priority: values.priority,
        user_notes: values.user_notes,
      });
      toast.success('Document updated.');
      onSaved(updated);
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
      title="Edit document details"
      description="Changes are saved to your copy of the analysis."
      width="max-w-xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        <div>
          <label className="label" htmlFor="doc-title">Title</label>
          <input
            id="doc-title"
            className="input"
            value={values.title}
            onChange={(event) => setValues({ ...values, title: event.target.value })}
            maxLength={255}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="doc-category">Category</label>
            <select
              id="doc-category"
              className="input"
              value={values.category}
              onChange={(event) => setValues({ ...values, category: event.target.value })}
            >
              {categories.map((category) => (
                <option key={category} value={category}>{category}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="label">Priority</label>
            <div className="flex gap-2">
              {PRIORITIES.map((priority) => (
                <button
                  key={priority}
                  type="button"
                  onClick={() => setValues({ ...values, priority })}
                  className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition ${
                    values.priority === priority
                      ? `${PRIORITY_STYLES[priority]} ring-2 ring-indigo-500/30`
                      : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'
                  }`}
                >
                  {priority}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div>
          <label className="label" htmlFor="doc-notes">Your notes</label>
          <textarea
            id="doc-notes"
            className="textarea !min-h-[110px]"
            placeholder="Add context for your team…"
            value={values.user_notes}
            onChange={(event) => setValues({ ...values, user_notes: event.target.value })}
            maxLength={5000}
          />
          <p className="mt-1 text-right text-xs text-slate-400">{values.user_notes.length}/5000</p>
        </div>

        <div className="flex justify-end gap-3 pt-1">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
