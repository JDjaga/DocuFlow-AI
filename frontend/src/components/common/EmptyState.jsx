/**
 * EmptyState - friendly "nothing here yet" screen with an action button.
 * Used by every table when a filter (or the account itself) has no data.
 */
import { motion } from 'framer-motion';
import { Inbox } from 'lucide-react';

export default function EmptyState({
  icon: Icon = Inbox,
  title = 'Nothing here yet',
  description = 'Items will appear here once they exist.',
  action,
}) {
  return (
    <div className="empty-state">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400"
      >
        <Icon className="h-7 w-7" />
      </motion.div>
      <div>
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">{description}</p>
      </div>
      {action}
    </div>
  );
}
