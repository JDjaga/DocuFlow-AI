/**
 * Document Analyzer - the core feature of DocuFlow AI.
 *
 * Flow implemented here:
 *   1. choose a PDF/TXT file OR paste text (validated in the browser)
 *   2. click "Analyze Document with AI"
 *   3. POST /api/documents/analyze (multipart) -> backend extracts text,
 *      runs the AI engine (Mock or Gemini), validates the JSON and saves
 *   4. render the structured result (summary, entities, category, priority,
 *      action items, observations)
 *   5. act on it: view, edit, create tasks, reanalyze, delete
 *
 * Duplicate submissions are blocked by the `processing` flag, and
 * "Reanalyze" updates the existing document instead of creating a copy.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, FilePlus2, RotateCcw, Sparkles, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import PageHeader from '../components/common/PageHeader';
import ConfirmDialog from '../components/common/ConfirmDialog';
import UploadZone from '../components/documents/UploadZone';
import ProcessingAnimation from '../components/documents/ProcessingAnimation';
import AiResults from '../components/documents/AiResults';
import DocumentChat from '../components/documents/DocumentChat';
import EditDocumentModal from '../components/documents/EditDocumentModal';
import CreateTasksModal from '../components/documents/CreateTasksModal';
import { analyzeDocument, deleteDocument, getDocument } from '../services/documents';
import { getErrorMessage } from '../services/api';
import { validateFile } from '../utils/validators';
import { DOCUMENT_TYPES } from '../utils/constants';

export default function Analyzer() {
  const navigate = useNavigate();

  const [inputMode, setInputMode] = useState('file');
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState('');
  const [text, setText] = useState('');
  const [textError, setTextError] = useState('');
  const [title, setTitle] = useState('');
  const [documentType, setDocumentType] = useState('task');

  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(null);
  const [serverError, setServerError] = useState('');

  const [result, setResult] = useState(null); // AnalysisResponse from the API
  const [editOpen, setEditOpen] = useState(false);
  const [tasksOpen, setTasksOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // ------------------------- input handling -------------------------
  function handleFileSelect(picked) {
    const validationError = validateFile(picked);
    if (validationError) {
      setFileError(validationError);
      setFile(null);
      return;
    }
    setFileError('');
    setFile(picked);
    setServerError('');
  }

  function clearAll() {
    setFile(null);
    setFileError('');
    setText('');
    setTextError('');
    setTitle('');
    setServerError('');
    setResult(null);
  }

  function validateInputs() {
    if (inputMode === 'file') {
      if (!file) {
        setFileError('Select a PDF or TXT file first.');
        return false;
      }
      return true;
    }

    if (!text.trim()) {
      setTextError('Paste some text before analyzing.');
      return false;
    }
    setTextError('');
    return true;
  }

  // ------------------------- main action -------------------------
  async function runAnalysis(payload) {
    setProcessing(true);
    setServerError('');
    setProgress(payload.file ? 0 : null);
    try {
      const response = await analyzeDocument(payload, setProgress);
      setResult(response);
      toast.success(response.message);
      // Automatic fallback happened -> tell the user honestly which
      // provider actually answered (e.g. "Google Gemini quota was
      // exhausted. OpenRouter was used for this request.").
      if (response.ai_provider_notice) {
        toast(response.ai_provider_notice, { icon: '⚠️', duration: 8000 });
      }
      return response;
    } catch (error) {
      const message = getErrorMessage(error);
      setServerError(message);
      toast.error(message);
      return null;
    } finally {
      setProcessing(false);
      setProgress(null);
    }
  }

  async function handleAnalyze(event) {
    event.preventDefault();
    if (processing || !validateInputs()) return;

    await runAnalysis(
      inputMode === 'file'
        ? { file, title, documentType }
        : { text, title, documentType }
    );
  }

  async function handleReanalyze() {
    if (processing || !result) return;
    // Reuse the stored extracted text so the same content is re-analyzed;
    // the backend updates the existing row (no duplicate document).
    await runAnalysis({ text: result.document.extracted_text, documentId: result.document.id });
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await deleteDocument(result.document.id);
      toast.success('Document deleted.');
      clearAll();
      setDeleteOpen(false);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setDeleting(false);
    }
  }

  async function refreshResult() {
    if (!result) return;
    try {
      const fresh = await getDocument(result.document.id);
      setResult((current) => (current ? { ...current, document: fresh } : current));
    } catch {
      // The document may have been deleted in another tab - keep the old data.
    }
  }

  const analyzedDocument = result?.document;

  return (
    <div>
      <PageHeader
        title="Document Analyzer"
        description="Upload a document or paste text - the AI engine returns a structured analysis."
        actions={
          (analyzedDocument || file || text) && (
            <button type="button" className="btn-secondary" onClick={clearAll} disabled={processing}>
              <RotateCcw className="h-4 w-4" /> Start over
            </button>
          )
        }
      />

      <div className="grid gap-6 lg:grid-cols-5">
        {/* ------------------------- input panel ------------------------- */}
        <form onSubmit={handleAnalyze} className="lg:col-span-2">
          <div className="card p-5">
            <div className="mb-4 flex rounded-lg bg-slate-100 p-1">
              {[
                { value: 'file', label: 'Upload file' },
                { value: 'text', label: 'Paste text' },
              ].map((tab) => (
                <button
                  key={tab.value}
                  type="button"
                  onClick={() => setInputMode(tab.value)}
                  className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
                    inputMode === tab.value
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {inputMode === 'file' ? (
              <UploadZone
                file={file}
                onFileSelect={handleFileSelect}
                onClear={() => {
                  setFile(null);
                  setFileError('');
                }}
                error={fileError}
                disabled={processing}
              />
            ) : (
              <div>
                <label className="label" htmlFor="document-text">Document text</label>
                <textarea
                  id="document-text"
                  className="textarea"
                  placeholder={
                    'Paste the content of a proposal, meeting note, report, contract or email…\n\nExample:\n"Please review the attached proposal and share feedback by 2026-12-01."'
                  }
                  value={text}
                  onChange={(event) => {
                    setText(event.target.value);
                    setTextError('');
                  }}
                  disabled={processing}
                  maxLength={40000}
                />
                <div className="mt-1.5 flex items-center justify-between">
                  <p className={`text-xs ${textError ? 'text-rose-600' : 'text-slate-400'}`}>
                    {textError || 'Nothing is sent until you press Analyze.'}
                  </p>
                  <span className="text-xs text-slate-400">{text.length.toLocaleString()} characters</span>
                </div>
                {text && (
                  <button
                    type="button"
                    className="mt-2 text-xs font-semibold text-slate-500 hover:text-rose-600"
                    onClick={() => {
                      setText('');
                      setTextError('');
                    }}
                    disabled={processing}
                  >
                    Clear text
                  </button>
                )}
              </div>
            )}

            {/* Document type: decides whether workflow tasks apply */}
            <div className="mt-4">
              <span className="label">Document type</span>
              <div className="grid gap-2 sm:grid-cols-2">
                {DOCUMENT_TYPES.map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => setDocumentType(type.value)}
                    disabled={processing}
                    className={`rounded-xl border px-3.5 py-3 text-left transition ${
                      documentType === type.value
                        ? 'border-indigo-400 bg-indigo-50 ring-1 ring-indigo-300'
                        : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    <span className="block text-sm font-semibold text-slate-900">{type.label}</span>
                    <span className="mt-1 block text-xs leading-relaxed text-slate-500">{type.hint}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4">
              <label className="label" htmlFor="document-title">
                Title <span className="font-normal text-slate-400">(optional)</span>
              </label>
              <input
                id="document-title"
                className="input"
                placeholder="e.g. Acme Corp - Q4 Proposal"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                disabled={processing}
                maxLength={255}
              />
            </div>

            <button type="submit" className="btn-primary mt-5 w-full" disabled={processing}>
              {processing ? (
                'Analyzing…'
              ) : (
                <>
                  <Sparkles className="h-4 w-4" /> Analyze Document with AI
                </>
              )}
            </button>

            {serverError && (
              <div className="mt-4 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-3 text-xs leading-relaxed text-rose-700">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{serverError}</span>
              </div>
            )}

            <div className="mt-4 border-t border-slate-100 pt-4">
              <p className="text-xs leading-relaxed text-slate-500">
                <span className="font-semibold text-slate-700">What happens next:</span> the backend extracts
                the text, calls the AI engine, validates the response with Pydantic, then stores the document
                and its action items in the database.
              </p>
            </div>
          </div>
        </form>

        {/* ------------------------- results panel ------------------------- */}
        <div className="lg:col-span-3">
          <AnimatePresence mode="wait">
            {processing ? (
              <motion.div key="processing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <ProcessingAnimation progress={progress} />
              </motion.div>
            ) : analyzedDocument ? (
              <motion.div
                key={`result-${analyzedDocument.id}`}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
              >
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="truncate text-lg font-semibold text-slate-900">{analyzedDocument.title}</h2>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {analyzedDocument.category} · analyzed{' '}
                      {new Date(analyzedDocument.updated_at).toLocaleString('en-GB')}
                      {analyzedDocument.task_count > 0 && ` · ${analyzedDocument.task_count} task(s) created`}
                    </p>
                  </div>
                  <button type="button" className="btn-secondary !py-2" onClick={() => navigate(`/documents?open=${analyzedDocument.id}`)}>
                    <FilePlus2 className="h-4 w-4" /> Open in Documents
                  </button>
                </div>

                <AiResults
                  document={analyzedDocument}
                  aiProvider={result.ai_provider}
                  aiNotice={result.ai_provider_notice}
                  actions={{
                    busy: processing,
                    onView: () => navigate(`/documents?open=${analyzedDocument.id}`),
                    onEdit: () => setEditOpen(true),
                    onCreateTasks: () => setTasksOpen(true),
                    onReanalyze: handleReanalyze,
                    onDelete: () => setDeleteOpen(true),
                  }}
                />

                <div className="mt-4">
                  <DocumentChat documentId={analyzedDocument.id} />
                </div>
              </motion.div>
            ) : (
              <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="card p-10">
                  <div className="empty-state !py-6">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                      <Sparkles className="h-7 w-7" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">Your analysis will appear here</h3>
                      <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">
                        A summary, extracted entities, a priority with an explanation, suggested action items
                        and observations - all stored so you can search, filter and manage them later.
                      </p>
                    </div>
                    <div className="mt-2 grid w-full max-w-md gap-2 text-left sm:grid-cols-2">
                      {[
                        'PDF and TXT uploads (max 10 MB)',
                        'Paste text directly',
                        'Mock AI needs no API key',
                        'Action items become tasks in one click',
                      ].map((item) => (
                        <div key={item} className="flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-2.5 text-xs text-slate-600">
                          <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400" />
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* ------------------------- modals ------------------------- */}
      <EditDocumentModal
        open={editOpen}
        document={analyzedDocument}
        onClose={() => setEditOpen(false)}
        onSaved={(updated) => setResult((current) => ({ ...current, document: updated }))}
      />

      <CreateTasksModal
        open={tasksOpen}
        document={analyzedDocument}
        onClose={() => setTasksOpen(false)}
        onCreated={refreshResult}
      />

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={handleDelete}
        loading={deleting}
        title="Delete this document?"
        message={`"${analyzedDocument?.title}" and its analysis will be permanently removed. Tasks created from it are kept but lose their link to this document.`}
        confirmLabel="Delete document"
      />
    </div>
  );
}
