/**
 * Documents page - search, filter, sort, paginate and manage documents.
 *
 * URL parameters (set by other screens and by the global top bar search):
 *   ?search=term   pre-fills the search box
 *   ?open=<id>     opens the details drawer for that document
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import PageHeader from '../components/common/PageHeader';
import ConfirmDialog from '../components/common/ConfirmDialog';
import DocumentFilters from '../components/documents/DocumentFilters';
import DocumentTable from '../components/documents/DocumentTable';
import DocumentDrawer from '../components/documents/DocumentDrawer';
import EditDocumentModal from '../components/documents/EditDocumentModal';
import CreateTasksModal from '../components/documents/CreateTasksModal';
import useDocuments, { DEFAULT_FILTERS } from '../hooks/useDocuments';
import { deleteDocument, getDocument } from '../services/documents';
import { getErrorMessage } from '../services/api';

export default function Documents() {
  const [searchParams, setSearchParams] = useSearchParams();
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
    categories,
    loading,
    error,
  } = useDocuments();

  const [selected, setSelected] = useState(null); // opened drawer document
  const [editTarget, setEditTarget] = useState(null);
  const [tasksTarget, setTasksTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // ---------- read ?search= and ?open= from the URL ----------
  useEffect(() => {
    const urlSearch = searchParams.get('search');
    if (urlSearch && urlSearch !== filters.search) {
      updateFilters({ search: urlSearch });
    }

    const openId = searchParams.get('open');
    if (openId) {
      getDocument(Number(openId))
        .then((document) => setSelected(document))
        .catch((requestError) => toast.error(getErrorMessage(requestError)))
        .finally(() => {
          // Remove the parameter so a refresh does not reopen the drawer.
          const params = new URLSearchParams(searchParams);
          params.delete('open');
          setSearchParams(params, { replace: true });
        });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const hasActiveFilters = useMemo(
    () =>
      Boolean(
        filters.search ||
          filters.category ||
          filters.priority ||
          filters.status ||
          filters.sort !== DEFAULT_FILTERS.sort
      ),
    [filters]
  );

  function clearFilters() {
    updateFilters({
      search: '',
      category: '',
      priority: '',
      status: '',
      sort: DEFAULT_FILTERS.sort,
    });
    const params = new URLSearchParams(searchParams);
    params.delete('search');
    setSearchParams(params, { replace: true });
  }

  async function openDocument(document) {
    try {
      const full = await getDocument(document.id);
      setSelected(full);
    } catch (requestError) {
      toast.error(getErrorMessage(requestError));
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteDocument(deleteTarget.id);
      toast.success('Document deleted.');
      if (selected?.id === deleteTarget.id) setSelected(null);
      setDeleteTarget(null);
      refresh();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setDeleting(false);
    }
  }

  const handleDrawerUpdate = useCallback((updated) => {
    setSelected(updated);
    refresh();
  }, [refresh]);

  return (
    <div>
      <PageHeader
        title="Documents"
        description="Every analyzed document, with server side search, filters and pagination."
        actions={
          <>
            <button type="button" className="btn-secondary" onClick={refresh} title="Refresh list">
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
            <Link to="/analyzer" className="btn-primary">
              <Plus className="h-4 w-4" /> Analyze new
            </Link>
          </>
        }
      />

      <div className="card overflow-hidden">
        <DocumentFilters
          filters={filters}
          categories={categories}
          total={total}
          onChange={(patch) => updateFilters(patch)}
          onClear={clearFilters}
        />

        {error && (
          <div className="border-b border-slate-100 bg-rose-50 px-5 py-3 text-sm text-rose-700">{error}</div>
        )}

        <DocumentTable
          items={items}
          loading={loading}
          page={page}
          pages={pages}
          total={total}
          pageSize={pageSize}
          onPageChange={goToPage}
          onView={openDocument}
          onEdit={(document) => setEditTarget(document)}
          onDelete={(document) => setDeleteTarget(document)}
          hasActiveFilters={hasActiveFilters}
          onClearFilters={clearFilters}
        />
      </div>

      {/* ---------- Drawer with the full analysis ---------- */}
      <DocumentDrawer
        document={selected}
        onClose={() => setSelected(null)}
        onUpdated={handleDrawerUpdate}
        onCreateTasks={() => setTasksTarget(selected)}
      />

      {/* ---------- Edit modal (works from the table and the drawer) ---------- */}
      <EditDocumentModal
        open={Boolean(editTarget)}
        document={editTarget}
        onClose={() => setEditTarget(null)}
        onSaved={(updated) => {
          if (selected?.id === updated.id) setSelected(updated);
          refresh();
        }}
      />

      <CreateTasksModal
        open={Boolean(tasksTarget)}
        document={tasksTarget}
        onClose={() => setTasksTarget(null)}
        onCreated={() => {
          if (tasksTarget) openDocument(tasksTarget);
          refresh();
        }}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        loading={deleting}
        title="Delete this document?"
        message={`"${deleteTarget?.title}" will be permanently removed. Tasks created from it are kept but lose their link.`}
        confirmLabel="Delete document"
      />
    </div>
  );
}
