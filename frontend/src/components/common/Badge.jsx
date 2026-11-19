/**
 * Badge - the pill used for priorities and statuses.
 * Colour rules come from utils/constants.js so a status always looks the
 * same on every page.
 */
export default function Badge({ label, className = '' }) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${className}`}
    >
      {label}
    </span>
  );
}
