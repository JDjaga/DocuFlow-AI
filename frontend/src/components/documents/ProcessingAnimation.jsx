/**
 * ProcessingAnimation - what the user sees while the AI request is running.
 *
 * The messages describe the pipeline the request is travelling through
 * (extracting, analyzing, validating, saving). They do NOT claim each step
 * has already finished - the request is a single round trip.
 */
import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { FileSearch, Loader2, ShieldCheck, Sparkles } from 'lucide-react';

const STAGES = [
  'Reading document…',
  'Extracting key information…',
  'Identifying important entities…',
  'Evaluating priority…',
  'Generating action items…',
];

export default function ProcessingAnimation({ progress }) {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setStage((current) => (current + 1) % STAGES.length);
    }, 1300);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6">
      {/* Scanning line moving down the panel. */}
      <motion.div
        className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-indigo-500/15 to-transparent"
        animate={{ y: ['0%', '340%'] }}
        transition={{ repeat: Infinity, duration: 2.4, ease: 'easeInOut' }}
      />

      <div className="relative flex items-center gap-3">
        <motion.span
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.6, ease: 'linear' }}
          className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600"
        >
          <Loader2 className="h-6 w-6" />
        </motion.span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-900">Analyzing your document</p>
          <AnimatePresence mode="wait">
            <motion.p
              key={stage}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2 }}
              className="mt-0.5 text-sm text-slate-500"
            >
              {STAGES[stage]}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>

      {/* Upload progress (only available while the file is uploading). */}
      {typeof progress === 'number' && progress < 100 && (
        <div className="relative mt-5">
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
            <motion.div
              className="h-full rounded-full bg-indigo-600"
              animate={{ width: `${progress}%` }}
              transition={{ ease: 'easeOut' }}
            />
          </div>
          <p className="mt-1.5 text-xs text-slate-400">Uploading… {progress}%</p>
        </div>
      )}

      {/* Shimmering result placeholders. */}
      <div className="relative mt-6 space-y-3">
        {[100, 82, 64].map((width, index) => (
          <motion.div
            key={width}
            className="h-4 overflow-hidden rounded bg-slate-100"
            style={{ width: `${width}%` }}
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ repeat: Infinity, duration: 1.6, delay: index * 0.2 }}
          />
        ))}
      </div>

      <div className="relative mt-6 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-3">
        {[
          { icon: FileSearch, text: 'Text extraction' },
          { icon: Sparkles, text: 'AI analysis' },
          { icon: ShieldCheck, text: 'Response validation' },
        ].map(({ icon: Icon, text }) => (
          <div key={text} className="flex items-center gap-2 text-xs text-slate-500">
            <Icon className="h-4 w-4 text-indigo-500" /> {text}
          </div>
        ))}
      </div>
    </div>
  );
}
