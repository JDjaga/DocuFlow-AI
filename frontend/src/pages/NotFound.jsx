/** NotFound - shown for unknown URLs (inside the app shell). */
import { Link } from 'react-router-dom';
import { Compass, Home } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="empty-state !py-24">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
        <Compass className="h-8 w-8" />
      </div>
      <div>
        <p className="text-4xl font-semibold text-slate-900">404</p>
        <h1 className="mt-2 text-base font-semibold text-slate-900">Page not found</h1>
        <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">
          The page you are looking for does not exist or may have been moved.
        </p>
      </div>
      <Link to="/dashboard" className="btn-primary">
        <Home className="h-4 w-4" /> Back to dashboard
      </Link>
    </div>
  );
}
