/**
 * AppRoutes - every URL of the application in one place.
 *
 *   /login, /register   public: redirect to /dashboard if already signed in
 *   /dashboard …        protected: needs a valid token, rendered inside the
 *                       AppLayout shell (sidebar + topbar)
 *   /                   redirects to /dashboard
 *   *                   404 page (inside the shell when signed in,
 *                       /login redirect when signed out)
 */
import { Navigate, Route, Routes } from 'react-router-dom';
import ProtectedRoute from '../components/layout/ProtectedRoute';
import AppLayout from '../components/layout/AppLayout';
import useAuth from '../hooks/useAuth';

import Login from '../pages/Login';
import Register from '../pages/Register';
import Dashboard from '../pages/Dashboard';
import Analyzer from '../pages/Analyzer';
import Documents from '../pages/Documents';
import Tasks from '../pages/Tasks';
import ApiHealth from '../pages/ApiHealth';
import Settings from '../pages/Settings';
import NotFound from '../pages/NotFound';

/** Signed-in users should never see the login/register screens again. */
function PublicOnly({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return null;
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : children;
}

export default function AppRoutes() {
  return (
    <Routes>
      {/* ---------- Public routes ---------- */}
      <Route
        path="/login"
        element={
          <PublicOnly>
            <Login />
          </PublicOnly>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnly>
            <Register />
          </PublicOnly>
        }
      />

      {/* ---------- Protected routes ---------- */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/analyzer" element={<Analyzer />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/health" element={<ApiHealth />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  );
}
