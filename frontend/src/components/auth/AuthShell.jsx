/**
 * AuthShell - shared layout for Login and Register.
 * Brand panel on the left (hidden on mobile) + form on the right.
 */
import { ScanText } from 'lucide-react';
import { motion } from 'framer-motion';

export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* ---------------- Brand panel ---------------- */}
      <div className="relative hidden w-1/2 flex-col justify-between bg-slate-900 p-10 lg:flex">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white">
            <ScanText className="h-5 w-5" />
          </span>
          <span className="text-[15px] font-semibold text-white">
            DocuFlow <span className="text-indigo-400">AI</span>
          </span>
        </div>

        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <h2 className="max-w-md text-3xl font-semibold leading-tight tracking-tight text-white">
            Turn Documents into Decisions.
          </h2>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-400">
            Upload proposals, reports, meeting notes or contracts. DocuFlow AI extracts a summary, key
            entities, a priority level and ready-to-track action items in seconds.
          </p>

          <div className="mt-8 grid max-w-md grid-cols-3 gap-3">
            {[
              ['Summaries', 'in seconds'],
              ['Action items', 'auto-extracted'],
              ['Priorities', 'explained'],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-slate-700/70 bg-slate-800/60 px-3 py-3">
                <p className="text-xs font-medium text-slate-300">{label}</p>
                <p className="mt-0.5 text-sm font-semibold text-white">{value}</p>
              </div>
            ))}
          </div>
        </motion.div>

        <p className="text-xs text-slate-500">Mock AI mode runs locally - no API key required.</p>
      </div>

      {/* ---------------- Form panel ---------------- */}
      <div className="flex w-full items-center justify-center px-4 py-10 sm:px-8 lg:w-1/2">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="w-full max-w-md"
        >
          <div className="mb-7 flex items-center gap-2.5 lg:hidden">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white">
              <ScanText className="h-5 w-5" />
            </span>
            <span className="text-[15px] font-semibold text-slate-900">
              DocuFlow <span className="text-indigo-600">AI</span>
            </span>
          </div>

          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
          <p className="mt-1.5 text-sm text-slate-500">{subtitle}</p>

          <div className="mt-7">{children}</div>

          {footer && <div className="mt-6 text-center text-sm text-slate-500">{footer}</div>}
        </motion.div>
      </div>
    </div>
  );
}
