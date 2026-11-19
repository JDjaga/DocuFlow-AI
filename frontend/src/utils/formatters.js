/** Small formatting helpers used across the UI. */

const DATE_OPTIONS = { day: '2-digit', month: 'short', year: 'numeric' };

/** "2026-11-17T13:52:05" -> "17 Nov 2026" */
export function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString('en-GB', DATE_OPTIONS);
}

/** Same as formatDate but with the time: "17 Nov 2026, 13:52" */
export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return `${date.toLocaleDateString('en-GB', DATE_OPTIONS)}, ${date.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
  })}`;
}

/** "just now", "5 min ago", "3 days ago" (used for created dates). */
export function timeAgo(value) {
  if (!value) return '—';
  const seconds = Math.floor((Date.now() - new Date(value).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days > 1 ? 's' : ''} ago`;
  return formatDate(value);
}

/** 1024 -> "1.0 KB" */
export function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB'];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

/** "Jane Doe" -> "JD" */
export function getInitials(name = '') {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
}

/** Time based welcome message for the dashboard. */
export function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

/** Due date helper: returns a colour class for overdue / due soon / normal. */
export function dueDateTone(dueDate, status) {
  if (!dueDate) return 'text-slate-500';
  if (status === 'completed') return 'text-slate-400';

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(dueDate);
  due.setHours(0, 0, 0, 0);

  if (due < today) return 'text-rose-600 font-medium';
  const days = Math.round((due - today) / 86400000);
  if (days <= 7) return 'text-amber-600 font-medium';
  return 'text-slate-600';
}
