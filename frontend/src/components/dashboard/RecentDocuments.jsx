/**
 * RecentDocuments - last 5 analyzed documents.
 * Pure presentation: the Dashboard page passes rows in.
 */
import { useNavigate } from 'react-router-dom';
import { ArrowRight, FileText } from 'lucide-react';
import Badge from '../common/Badge';
import EmptyState from '../common/EmptyState';
import { SkeletonRow } from '../common/Skeleton';
import { formatDate } from '../../utils/formatters';
import { PRIORITY_STYLES, PROCESSING_STATUS_STYLES } from '../../utils/constants';

export default function RecentDocuments({ items = [], loading = false }) {
  const navigate = useNavigate();

  return (
    <section className="card overflow-hidden">
      <div className="card-header">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Recent Documents</h2>
          <p className="mt-0.5 text-xs text-slate-500">Latest analyses, newest first</p>
        </div>
        <button type="button" className="btn-ghost !px-3 !py-1.5" onClick={() => navigate('/documents')}>
          View all <ArrowRight className="h-4 w-4" />
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse">
          <thead className="bg-slate-50/70">
            <tr>
              <th className="th">Document</th>
              <th className="th">Category</th>
              <th className="th">Priority</th>
              <th className="th">Status</th>
              <th className="th">Created</th>
              <th className="th text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              Array.from({ length: 3 }).map((_, index) => <SkeletonRow key={index} columns={6} />)}

            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={6}>
                  <EmptyState
                    icon={FileText}
                    title="No documents yet"
                    description="Analyze your first document and it will show up here."
                  />
                </td>
              </tr>
            )}

            {!loading &&
              items.map((document) => (
                <tr key={document.id} className="border-b border-slate-100 transition last:border-0 hover:bg-slate-50/60">
                  <td className="td">
                    <p className="max-w-[240px] truncate font-medium text-slate-900">{document.title}</p>
                    {document.original_filename && (
                      <p className="mt-0.5 max-w-[240px] truncate text-xs text-slate-400">
                        {document.original_filename}
                      </p>
                    )}
                  </td>
                  <td className="td text-slate-600">{document.category}</td>
                  <td className="td">
                    <Badge label={document.priority} className={PRIORITY_STYLES[document.priority]} />
                  </td>
                  <td className="td">
                    <Badge
                      label={document.processing_status.replace('_', ' ')}
                      className={PROCESSING_STATUS_STYLES[document.processing_status]}
                    />
                  </td>
                  <td className="td text-slate-500">{formatDate(document.created_at)}</td>
                  <td className="td text-right">
                    <button
                      type="button"
                      className="text-sm font-semibold text-indigo-600 hover:text-indigo-700"
                      onClick={() => navigate(`/documents?open=${document.id}`)}
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
