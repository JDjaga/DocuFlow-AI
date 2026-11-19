/** Pagination - page buttons + "showing X–Y of Z", used by both tables. */
import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function Pagination({ page, pages, total, pageSize, onPageChange }) {
  if (total === 0) return null;

  const firstItem = (page - 1) * pageSize + 1;
  const lastItem = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-col items-center justify-between gap-3 border-t border-slate-100 px-5 py-3.5 sm:flex-row">
      <p className="text-sm text-slate-500">
        Showing <span className="font-medium text-slate-700">{firstItem}</span>–
        <span className="font-medium text-slate-700">{lastItem}</span> of{' '}
        <span className="font-medium text-slate-700">{total}</span>
      </p>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="btn-secondary !px-3 !py-1.5"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        <span className="text-sm text-slate-600">
          Page <span className="font-medium">{page}</span> of {pages}
        </span>

        <button
          type="button"
          className="btn-secondary !px-3 !py-1.5"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages}
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
