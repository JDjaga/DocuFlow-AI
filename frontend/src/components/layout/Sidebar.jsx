/**
 * Sidebar - main navigation.
 *
 * Desktop: sticky, can be collapsed to icons only (with tooltips).
 * Mobile:  hidden, opened as a slide-over by the hamburger in the Topbar.
 */
import { NavLink, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { PanelLeftClose, PanelLeftOpen, ScanText, X } from 'lucide-react';
import { NAV_ITEMS } from '../../utils/constants';

function Logo({ compact }) {
  return (
    <div className="flex items-center gap-2.5 overflow-hidden">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white">
        <ScanText className="h-5 w-5" />
      </span>
      {!compact && (
        <span className="whitespace-nowrap text-[15px] font-semibold tracking-tight text-slate-900">
          DocuFlow <span className="text-indigo-600">AI</span>
        </span>
      )}
    </div>
  );
}

function Navigation({ collapsed, onNavigate }) {
  const location = useLocation();

  return (
    <nav className="flex-1 space-y-1 px-3 py-4">
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
        const active = location.pathname === to || location.pathname.startsWith(`${to}/`);

        return (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            title={collapsed ? label : undefined}
            className={`group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
              active
                ? 'bg-indigo-50 text-indigo-700'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            } ${collapsed ? 'justify-center px-2' : ''}`}
          >
            {/* Active indicator bar on the left edge. */}
            {active && (
              <motion.span
                layoutId="sidebar-active"
                className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full bg-indigo-600"
              />
            )}
            <Icon className={`h-[18px] w-[18px] shrink-0 ${active ? 'text-indigo-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
            {!collapsed && <span className="truncate">{label}</span>}

            {/* Tooltip shown only while the sidebar is collapsed. */}
            {collapsed && (
              <span className="pointer-events-none absolute left-full z-50 ml-2 hidden whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-white shadow-lg group-hover:block">
                {label}
              </span>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}

export default function Sidebar({ collapsed, mobileOpen, onCloseMobile, onToggleCollapse }) {
  return (
    <>
      {/* ---------------- Desktop sidebar ---------------- */}
      <aside
        className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-slate-200 bg-white transition-[width] duration-200 lg:flex ${
          collapsed ? 'w-[76px]' : 'w-64'
        }`}
      >
        <div className={`flex h-16 items-center border-b border-slate-100 ${collapsed ? 'justify-center px-3' : 'justify-between px-5'}`}>
          <Logo compact={collapsed} />
          {!collapsed && (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
              aria-label="Collapse sidebar"
            >
              <PanelLeftClose className="h-5 w-5" />
            </button>
          )}
        </div>

        {collapsed && (
          <div className="flex justify-center border-b border-slate-100 py-2">
            <button
              type="button"
              onClick={onToggleCollapse}
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
              aria-label="Expand sidebar"
            >
              <PanelLeftOpen className="h-5 w-5" />
            </button>
          </div>
        )}

        <Navigation collapsed={collapsed} />

        {!collapsed && (
          <div className="border-t border-slate-100 px-5 py-4">
            <p className="text-xs leading-relaxed text-slate-400">
              Turn Documents into Decisions.
            </p>
          </div>
        )}
      </aside>

      {/* ---------------- Mobile slide-over ---------------- */}
      <AnimatePresence>
        {mobileOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <motion.div
              className="absolute inset-0 bg-slate-900/40"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onCloseMobile}
            />
            <motion.aside
              className="absolute left-0 top-0 flex h-full w-72 max-w-[85vw] flex-col bg-white shadow-2xl"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 320, damping: 32 }}
            >
              <div className="flex h-16 items-center justify-between border-b border-slate-100 px-5">
                <Logo />
                <button
                  type="button"
                  onClick={onCloseMobile}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
                  aria-label="Close menu"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <Navigation collapsed={false} onNavigate={onCloseMobile} />
            </motion.aside>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
