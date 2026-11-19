/**
 * Topbar - sticky header present on every authenticated page.
 *
 * Contains, all of it functional:
 *   - hamburger (mobile sidebar)
 *   - current page title
 *   - global search  -> navigates to /documents?search=…
 *   - AI mode badge  -> real data from GET /api/health/ai (Mock / Gemini /
 *                       OpenRouter / Ollama - whichever is active)
 *   - notifications  -> your real pending tasks from GET /api/tasks
 *   - user menu with Settings and Logout
 */
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Bell, LogOut, Menu, Search, Settings, Sparkles, UserRound } from 'lucide-react';
import toast from 'react-hot-toast';
import useAuth from '../../hooks/useAuth';
import { getInitials } from '../../utils/formatters';
import { NAV_ITEMS } from '../../utils/constants';
import { fetchAiHealth } from '../../services/health';
import { listTasks } from '../../services/tasks';
import { getErrorMessage } from '../../services/api';
import Badge from '../common/Badge';

// Short labels for the topbar badge (full labels live in the health API).
const SHORT_PROVIDER_LABELS = {
  mock: 'Mock AI',
  gemini: 'Gemini',
  openrouter: 'OpenRouter',
  ollama: 'Ollama',
};

function useOutsideClick(ref, onOutside) {
  useEffect(() => {
    function handleClick(event) {
      if (ref.current && !ref.current.contains(event.target)) onOutside();
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [ref, onOutside]);
}

export default function Topbar({ onMenuClick }) {
  const { user, signOut } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [searchTerm, setSearchTerm] = useState('');
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [aiMode, setAiMode] = useState(null);
  const [pendingTasks, setPendingTasks] = useState([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [notificationsLoaded, setNotificationsLoaded] = useState(false);

  const userMenuRef = useRef(null);
  const notificationsRef = useRef(null);
  useOutsideClick(userMenuRef, () => setUserMenuOpen(false));
  useOutsideClick(notificationsRef, () => setNotificationsOpen(false));

  // Page title from the navigation config.
  const currentNav = NAV_ITEMS.find((item) => location.pathname.startsWith(item.to));
  const pageTitle = currentNav?.label || (location.pathname === '/' ? 'Dashboard' : 'DocuFlow AI');

  // AI mode badge (which provider is active) - loaded once.
  useEffect(() => {
    let active = true;
    fetchAiHealth()
      .then((data) => {
        if (active) setAiMode(data);
      })
      .catch(() => {
        if (active) setAiMode({ mode: 'AI status unavailable', provider: 'unknown' });
      });
    return () => {
      active = false;
    };
  }, []);

  // Notifications: real pending tasks, fetched when the bell is opened.
  useEffect(() => {
    if (!notificationsOpen) return;
    let active = true;

    listTasks({ status: 'pending', page: 1, page_size: 5 })
      .then((data) => {
        if (!active) return;
        setPendingTasks(data.items);
        setPendingCount(data.total);
        setNotificationsLoaded(true);
      })
      .catch((error) => {
        if (active) toast.error(getErrorMessage(error));
      });

    return () => {
      active = false;
    };
  }, [notificationsOpen]);

  function handleSearch(event) {
    event.preventDefault();
    const term = searchTerm.trim();
    navigate(term ? `/documents?search=${encodeURIComponent(term)}` : '/documents');
    setSearchTerm('');
  }

  function handleLogout() {
    signOut();
    toast.success('Signed out successfully.');
    navigate('/login', { replace: true });
  }

  const isMock = aiMode?.provider === 'mock';

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/85 backdrop-blur">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
        {/* Mobile menu */}
        <button
          type="button"
          onClick={onMenuClick}
          className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 lg:hidden"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Page title */}
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900 sm:text-base">{pageTitle}</p>
        </div>

        {/* Global search */}
        <form onSubmit={handleSearch} className="relative ml-auto hidden md:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search documents…"
            aria-label="Search documents"
            className="input w-64 !py-2 !pl-9"
          />
        </form>

        {/* AI mode indicator - the UI must never hide which mode is active */}
        {aiMode && (
          <span
            title={`AI provider: ${aiMode.mode}`}
            className={`hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium sm:inline-flex ${
              isMock ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            {SHORT_PROVIDER_LABELS[aiMode.provider] || 'AI'}
          </span>
        )}

        {/* Notifications */}
        <div className="relative" ref={notificationsRef}>
          <button
            type="button"
            onClick={() => setNotificationsOpen((open) => !open)}
            className="relative rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
            aria-label="Notifications"
          >
            <Bell className="h-5 w-5" />
            {pendingCount > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-indigo-600 px-1 text-[10px] font-semibold text-white">
                {pendingCount > 99 ? '99+' : pendingCount}
              </span>
            )}
          </button>

          <AnimatePresence>
            {notificationsOpen && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 6, scale: 0.98 }}
                className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
              >
                <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                  <p className="text-sm font-semibold text-slate-900">Pending tasks</p>
                  <Badge label={`${pendingCount}`} className="border-slate-200 bg-slate-100 text-slate-600" />
                </div>

                <div className="max-h-72 overflow-y-auto">
                  {!notificationsLoaded ? (
                    <p className="px-4 py-6 text-center text-sm text-slate-500">Loading…</p>
                  ) : pendingTasks.length === 0 ? (
                    <p className="px-4 py-6 text-center text-sm text-slate-500">
                      You have no pending tasks. 🎉
                    </p>
                  ) : (
                    pendingTasks.map((task) => (
                      <Link
                        key={task.id}
                        to="/tasks"
                        onClick={() => setNotificationsOpen(false)}
                        className="block border-b border-slate-50 px-4 py-3 transition last:border-0 hover:bg-slate-50"
                      >
                        <p className="truncate text-sm font-medium text-slate-800">{task.title}</p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          {task.priority} priority
                          {task.due_date ? ` · due ${task.due_date}` : ''}
                          {task.document_title ? ` · ${task.document_title}` : ''}
                        </p>
                      </Link>
                    ))
                  )}
                </div>

                <Link
                  to="/tasks"
                  onClick={() => setNotificationsOpen(false)}
                  className="block bg-slate-50 px-4 py-2.5 text-center text-xs font-semibold text-indigo-600 hover:bg-slate-100"
                >
                  View all tasks
                </Link>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* User menu */}
        <div className="relative" ref={userMenuRef}>
          <button
            type="button"
            onClick={() => setUserMenuOpen((open) => !open)}
            className="flex items-center gap-2 rounded-lg p-1 transition hover:bg-slate-100"
            aria-label="User menu"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
              {getInitials(user?.full_name || '?')}
            </span>
            <span className="hidden text-left lg:block">
              <span className="block max-w-[140px] truncate text-sm font-medium text-slate-800">
                {user?.full_name}
              </span>
            </span>
          </button>

          <AnimatePresence>
            {userMenuOpen && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 6, scale: 0.98 }}
                className="absolute right-0 z-50 mt-2 w-60 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
              >
                <div className="border-b border-slate-100 px-4 py-3">
                  <p className="truncate text-sm font-semibold text-slate-900">{user?.full_name}</p>
                  <p className="truncate text-xs text-slate-500">{user?.email}</p>
                </div>

                <Link
                  to="/settings"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-slate-700 transition hover:bg-slate-50"
                >
                  <Settings className="h-4 w-4 text-slate-400" /> Settings
                </Link>
                <Link
                  to="/health"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-slate-700 transition hover:bg-slate-50"
                >
                  <UserRound className="h-4 w-4 text-slate-400" /> Account
                </Link>

                <button
                  type="button"
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2.5 border-t border-slate-100 px-4 py-2.5 text-sm text-rose-600 transition hover:bg-rose-50"
                >
                  <LogOut className="h-4 w-4" /> Log out
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}
