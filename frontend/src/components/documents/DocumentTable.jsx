/**
 * DocumentTable - the documents list with pagination.
 * Filtering happens on the backend; this component only renders rows.
 */
import { FileText, Pencil, Trash2, Eye } from 'lucide-react';
import Badge from '../common/Badge';
import EmptyState from '../common/EmptyState';
import Pagination from '../common/Pagination';
import { SkeletonRow } from '../common/Skeleton';
import { formatDateTime } from '../../utils/formatters';
import { PRIORITY_STYLES, PROCESSING_STATUS_STYLES, DOCUMENT_TYPE_LABELS, DOCUMENT_TYPE_STYLES } from '../../utils/constants';

export default function DocumentTable({
  items,
  loading,
  page,
  pages,
  total,
  pageSize,
  onPageChange,
  onView,
  onEdit,
  onDelete,
  hasActiveFilters = false,
  onClearFilters,
}) {
  if (!loading && items.length === 0) {
    return (
      <div className="px-5 py-4">
        <EmptyState
          icon={FileText}
          title={hasActiveFilters ? 'No documents match your filters' : 'No documents yet'}
          description={
            hasActiveFilters
              ? 'Try a different search term or clear the filters to see everything.'
              : 'Analyze your first document in the Document Analyzer and it will appear here.'
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
        <table className="w-full min-w-[860px] border-collapse">
          <thead className="bg-slate-50/70">
            <tr>
              <th className="th">Document</th>
              <th className="th">Category</th>
              <th className="th">Type</th>
              <th className="th">Priority</th>
              <th className="th">Status</th>
              <th className="th">Created</th>
              <th className="th">Updated</th>
              <th className="th text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              Array.from({ length: 5 }).map((_, index) => <SkeletonRow key={index} columns={8} />)}

            {!loading &&
              items.map((document) => (
                <tr
                  key={document.id}
                  className="cursor-pointer border-b border-slate-100 transition last:border-0 hover:bg-slate-50/70"
                  onClick={() => onView(document)}
                >
                  <td className="td">
                    <div className="flex items-center gap-3">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                        <FileText className="h-4 w-4" />
                      </span>
                      <div className="min-w-0">
                        <p className="max-w-[260px] truncate font-medium text-slate-900">{document.title}</p>
                        <p className="max-w-[260px] truncate text-xs text-slate-400">
                          {document.original_filename || `Document #${document.id}`}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="td text-slate-600">{document.category}</td>
                  <td className="td">
                    <Badge
                      label={DOCUMENT_TYPE_LABELS[document.document_type] || 'General'}
                      className={DOCUMENT_TYPE_STYLES[document.document_type] || DOCUMENT_TYPE_STYLES.general}
                    />
                  </td>
                  <td className="td">
                    <Badge label={document.priority} className={PRIORITY_STYLES[document.priority]} />
                  </td>
                  <td className="td">
                    <Badge
                      label={document.processing_status.replace('_', ' ')}
                      className={PROCESSING_STATUS_STYLES[document.processing_status]}
                    />
                  </td>
                  <td className="td whitespace-nowrap text-slate-500">{formatDateTime(document.created_at)}</td>
                  <td className="td whitespace-nowrap text-slate-500">{formatDateTime(document.updated_at)}</td>
                  <td className="td">
                    <div className="flex items-center justify-end gap-1" onClick={(event) => event.stopPropagation()}>
                      <button
                        type="button"
                        className="rounded-lg p-2 text-slate-400 transition hover:bg-indigo-50 hover:text-indigo-600"
                        onClick={() => onView(document)}
                        title="View details"
                        aria-label={`View ${document.title}`}
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                        onClick={() => onEdit(document)}
                        title="Edit details"
                        aria-label={`Edit ${document.title}`}
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        className="rounded-lg p-2 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                        onClick={() => onDelete(document)}
                        title="Delete"
                        aria-label={`Delete ${document.title}`}
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

      <Pagination
        page={page}
        pages={pages}
        total={total}
        pageSize={pageSize}
        onPageChange={onPageChange}
      />
    </>
  );
}
