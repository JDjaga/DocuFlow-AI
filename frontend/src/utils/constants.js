/**
 * Shared constants: the fixed vocabulary of the UI.
 *
 * These values MUST match the backend (backend/app/core/constants.py) so a
 * filter value sent from React is always accepted by FastAPI.
 */
import {
  LayoutDashboard,
  ScanText,
  FileText,
  ListChecks,
  Activity,
  Settings,
} from 'lucide-react';

export const PRIORITIES = ['High', 'Medium', 'Low'];

export const TASK_STATUSES = [
  { value: 'pending', label: 'Pending' },
  { value: 'in_review', label: 'In Review' },
  { value: 'completed', label: 'Completed' },
];

export const PROCESSING_STATUSES = [
  { value: 'completed', label: 'Completed' },
  { value: 'pending', label: 'Pending' },
  { value: 'failed', label: 'Failed' },
];

export const DOCUMENT_CATEGORIES = [
  'Business Proposal',
  'Meeting Notes',
  'Technical Report',
  'Financial Document',
  'Customer Feedback',
  'Project Report',
  'General Document',
];

/** Document types chosen before analysis (must match backend constants). */
export const DOCUMENT_TYPES = [
  {
    value: 'task',
    label: 'Task / work document',
    hint: 'Proposals, reports, meeting notes - AI suggests action items that become workflow tasks.',
  },
  {
    value: 'general',
    label: 'General document',
    hint: 'Reference material, policies, articles - analysis and chat only, no workflow tasks.',
  },
];

export const DOCUMENT_TYPE_STYLES = {
  task: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  general: 'bg-slate-100 text-slate-600 border-slate-200',
};

export const DOCUMENT_TYPE_LABELS = {
  task: 'Task / work',
  general: 'General',
};

/** Tailwind classes per priority - one source of truth for every badge. */
export const PRIORITY_STYLES = {
  High: 'bg-rose-50 text-rose-700 border-rose-200',
  Medium: 'bg-amber-50 text-amber-700 border-amber-200',
  Low: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

export const TASK_STATUS_STYLES = {
  pending: 'bg-slate-100 text-slate-700 border-slate-200',
  in_review: 'bg-amber-50 text-amber-700 border-amber-200',
  completed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

export const PROCESSING_STATUS_STYLES = {
  completed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  pending: 'bg-amber-50 text-amber-700 border-amber-200',
  failed: 'bg-rose-50 text-rose-700 border-rose-200',
};

/** Sidebar navigation. `role` marks where each item appears. */
export const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/analyzer', label: 'Document Analyzer', icon: ScanText },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/tasks', label: 'Workflow Tasks', icon: ListChecks },
  { to: '/health', label: 'API Health', icon: Activity },
  { to: '/settings', label: 'Settings', icon: Settings },
];

/** Upload rules shown to the user before a file leaves the browser. */
export const MAX_FILE_SIZE_MB = 10;
export const ALLOWED_EXTENSIONS = ['.pdf', '.txt'];
