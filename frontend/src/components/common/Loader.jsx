/** Loader - centred spinner with an optional label (page/section loading). */
import { motion } from 'framer-motion';

export default function Loader({ label = 'Loading…', className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 py-14 ${className}`} role="status">
      <motion.div
        className="h-9 w-9 rounded-full border-2 border-slate-200 border-t-indigo-600"
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 0.8, ease: 'linear' }}
      />
      <p className="text-sm text-slate-500">{label}</p>
    </div>
  );
}
