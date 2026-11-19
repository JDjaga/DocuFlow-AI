/**
 * ProtectedRoute - the security gate in front of every private page.
 *
 * Behaviour:
 *   1. while the session is being restored, show a loader (never flash the login page)
 *   2. if there is no user, redirect to /login and remember where they were going
 *   3. otherwise render the page
 */
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import Loader from '../common/Loader';
import useAuth from '../../hooks/useAuth';

export default function ProtectedRoute() {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Loader label="Restoring your session…" />
      </div>
    );
  }

  if (!isAuthenticated) {
    // `state.from` lets us return the user to the page they asked for.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
