/**
 * Skeleton - shimmering placeholder used while a table or card loads.
 * Prevents the layout from jumping when real data arrives.
 */
export function SkeletonRow({ columns = 5 }) {
  return (
    <tr className="animate-pulse border-b border-slate-100 last:border-0">
      {Array.from({ length: columns }).map((_, index) => (
        <td key={index} className="px-5 py-4">
          <div className="h-3.5 rounded bg-slate-200/80" style={{ width: `${55 + ((index * 13) % 40)}%` }} />
        </td>
      ))}
    </tr>
  );
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="animate-pulse space-y-3 p-5">
      <div className="h-4 w-1/3 rounded bg-slate-200" />
      {Array.from({ length: lines }).map((_, index) => (
        <div key={index} className="h-3 rounded bg-slate-200" style={{ width: `${90 - index * 15}%` }} />
      ))}
    </div>
  );
}

export default SkeletonCard;
