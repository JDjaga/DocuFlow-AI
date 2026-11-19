/**
 * DocumentDrawer - right hand slide-over with the complete analysis.
 *
 * Sections:
 *   - metadata (status, priority, category, dates, task count)
 *   - AI summary and priority explanation
 *   - key entities
 *   - suggested action items (with a button to create them as tasks)
 *   - user notes (editable, saved with PUT /api/documents/{id})
 *   - original extracted text
 *
 * Motion: spring based slide-in, Escape closes it.
 */
import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { CalendarDays, Layers, ListPlus, Save, Tags, X } from 'lucide-react';
import toast from 'react-hot-toast';
import Badge from '../common/Badge';
import DocumentChat from './DocumentChat';
import { updateDocument } from '../../services/documents';
import { getErrorMessage } from '../../services/api';
import { formatDateTime, formatDate } from '../../utils/formatters';
import { PRIORITY_STYLES, PROCESSING_STATUS_STYLES, DOCUMENT_TYPE_LABELS, DOCUMENT_TYPE_STYLES } from '../../utils/constants';

function DetailRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-3 py-2.5">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
      <div className="min-w-0">
        <p className="text-xs text-slate-400">{label}</p>
        <div className="mt-0.5 text-sm text-slate-800">{value}</div>
      </div>
    </div>
  );
}

export default function DocumentDrawer({ document, onClose, onUpdated, onCreateTasks }) {
  const isGeneral = document?.document_type === 'general';
  const [notes, setNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

  // Reload local edit state whenever a different document is opened.
  useEffect(() => {
    setNotes(document?.user_notes || '');
    setShowOriginal(false);
  }, [document]);

  // Close with the Escape key.
  // NOTE: the prop is named `document`, so we always use `window`/element
  // references explicitly instead of the DOM's global `document`.
  useEffect(() => {
    if (!document) return undefined;
    function onKeyDown(event) {
      if (event.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [document, onClose]);

  async function saveNotes() {
    setSavingNotes(true);
    try {
      const updated = await updateDocument(document.id, { user_notes: notes });
      toast.success('Notes saved.');
      onUpdated(updated);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setSavingNotes(false);
    }
  }

  const notesDirty = document && notes !== (document.user_notes || '');

  return (
    <AnimatePresence>
      {document && (
        <div className="fixed inset-0 z-50">
          <motion.div
            className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-label={`Details for ${document.title}`}
            className="absolute right-0 top-0 flex h-full w-full max-w-xl flex-col bg-white shadow-2xl"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 300, damping: 32 }}
          >
            {/* Header */}
            <header className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-4">
              <div className="min-w-0">
                <h2 className="truncate text-base font-semibold text-slate-900">{document.title}</h2>
                <p className="mt-0.5 truncate text-xs text-slate-500">
                  {document.original_filename || 'Pasted text'} · ID {document.id}
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                aria-label="Close details"
              >
                <X className="h-5 w-5" />
              </button>
            </header>

            <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">
              {/* Status + priority */}
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  label={document.processing_status.replace('_', ' ')}
                  className={PROCESSING_STATUS_STYLES[document.processing_status]}
                />
                <Badge label={document.priority} className={PRIORITY_STYLES[document.priority]} />
                <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700">
                  {document.category}
                </span>
                <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${DOCUMENT_TYPE_STYLES[document.document_type] || DOCUMENT_TYPE_STYLES.general}`}>
                  {DOCUMENT_TYPE_LABELS[document.document_type] || 'General'}
                </span>
              </div>

              {/* Metadata */}
              <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 px-4 py-1">
                <DetailRow icon={CalendarDays} label="Created" value={formatDateTime(document.created_at)} />
                <DetailRow icon={CalendarDays} label="Last updated" value={formatDateTime(document.updated_at)} />
                <DetailRow icon={Tags} label="Category" value={document.category} />
                <DetailRow icon={Layers} label="Linked tasks" value={`${document.task_count} task(s)`} />
              </div>

              {/* Summary */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-slate-900">Summary</h3>
                <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm leading-relaxed text-slate-700">
                  {document.summary}
                </p>
              </section>

              {/* Priority explanation */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-slate-900">Priority explanation</h3>
                <p className="text-sm leading-relaxed text-slate-600">{document.priority_reason}</p>
              </section>

              {/* Entities */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-slate-900">
                  Key entities ({document.key_entities.length})
                </h3>
                {document.key_entities.length === 0 ? (
                  <p className="text-sm text-slate-500">No entities detected.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {document.key_entities.map((entity, index) => (
                      <span
                        key={`${entity.type}-${index}`}
                        className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs"
                      >
                        <span className="font-semibold text-slate-500">{entity.type}:</span>{' '}
                        <span className="text-slate-800">{entity.value}</span>
                      </span>
                    ))}
                  </div>
                )}
              </section>

              {/* Action items */}
              <section>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-900">
                    Action items ({document.action_items.length})
                  </h3>
                  {!isGeneral && document.action_items.length > 0 && (
                    <button type="button" className="text-xs font-semibold text-indigo-600 hover:text-indigo-700" onClick={onCreateTasks}>
                      <ListPlus className="mr-1 inline h-3.5 w-3.5" /> Create tasks
                    </button>
                  )}
                </div>
                {isGeneral ? (
                  <p className="text-sm text-slate-500">
                    General document - action items and workflow tasks are disabled. Use chat to ask questions about it.
                  </p>
                ) : document.action_items.length === 0 ? (
                  <p className="text-sm text-slate-500">No action items suggested.</p>
                ) : (
                  <ul className="space-y-2">
                    {document.action_items.map((item, index) => (
                      <li key={index} className="rounded-lg border border-slate-200 px-3.5 py-2.5">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-medium text-slate-900">{item.title}</p>
                          <Badge
                            label={item.priority}
                            className={PRIORITY_STYLES[item.priority] || 'border-slate-200 bg-slate-100 text-slate-600'}
                          />
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          {item.due_date ? `Due ${formatDate(item.due_date)}` : 'No due date'}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* Observations */}
              {document.observations.length > 0 && (
                <section>
                  <h3 className="mb-2 text-sm font-semibold text-slate-900">Observations</h3>
                  <ul className="space-y-1.5">
                    {document.observations.map((observation, index) => (
                      <li key={index} className="flex gap-2 text-sm text-slate-600">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400" />
                        {observation}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Chat with this document */}
              <DocumentChat documentId={document.id} />

              {/* User notes */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-slate-900">Your notes</h3>
                <textarea
                  className="textarea !min-h-[100px]"
                  placeholder="Add context, decisions or follow-up information…"
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  maxLength={5000}
                />
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-xs text-slate-400">{notes.length}/5000</span>
                  <button
                    type="button"
                    className="btn-primary !py-2"
                    onClick={saveNotes}
                    disabled={savingNotes || !notesDirty}
                  >
                    <Save className="h-4 w-4" /> {savingNotes ? 'Saving…' : 'Save notes'}
                  </button>
                </div>
              </section>

              {/* Original text */}
              <section className="pb-4">
                <button
                  type="button"
                  className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                  onClick={() => setShowOriginal((value) => !value)}
                >
                  {showOriginal ? 'Hide original text' : 'Show original text'}
                  <span className="text-xs text-slate-400">{document.extracted_text.length.toLocaleString()} chars</span>
                </button>
                {showOriginal && (
                  <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-xs leading-relaxed text-slate-700">
                    {document.extracted_text}
                  </pre>
                )}
              </section>
            </div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  );
}
