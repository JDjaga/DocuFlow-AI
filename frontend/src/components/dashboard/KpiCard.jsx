/**
 * KpiCard - one statistic tile on the dashboard.
 * Values always come from GET /api/dashboard/stats (never invented).
 */
import { motion } from 'framer-motion';

export default function KpiCard({ icon: Icon, label, value, hint, accent = 'indigo', index = 0 }) {
  const accents = {
    indigo: 'bg-indigo-50 text-indigo-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-600',
    rose: 'bg-rose-50 text-rose-600',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.07, duration: 0.35, ease: 'easeOut' }}
      whileHover={{ y: -3 }}
      className="card p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">
            {value ?? '—'}
          </p>
        </div>
        <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${accents[accent]}`}>
          <Icon className="h-5 w-5" />
        </span>
      </div>
      {hint && <p className="mt-3 text-xs text-slate-400">{hint}</p>}
    </motion.div>
  );
}
