/**
 * AuthContext - knows WHO is logged in for the whole application.
 *
 * WHAT THIS FILE DOES
 *   - restores an existing session on page refresh (GET /api/auth/me)
 *   - exposes signIn / signUp / signOut to every component
 *   - exposes `loading` so routes can wait before deciding to redirect
 *
 * WHY IT EXISTS
 *   The top bar, the protected routes and several pages all need the
 *   current user. Passing it through props everywhere would be messy.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { fetchCurrentUser, login as loginRequest, logout as logoutRequest, register as registerRequest } from '../services/auth';
import { getToken } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // On first render: if a token exists, ask the API who it belongs to.
  useEffect(() => {
    let active = true;

    async function restoreSession() {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const profile = await fetchCurrentUser();
        if (active) setUser(profile);
      } catch {
        // Invalid/expired token: api.js already cleared it.
        if (active) setUser(null);
      } finally {
        if (active) setLoading(false);
      }
    }

    restoreSession();
    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(async (email, password) => {
    const profile = await loginRequest({ email, password });
    setUser(profile);
    return profile;
  }, []);

  const signUp = useCallback(async (payload) => {
    const profile = await registerRequest(payload);
    setUser(profile);
    return profile;
  }, []);

  const signOut = useCallback(() => {
    logoutRequest();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, isAuthenticated: Boolean(user), signIn, signUp, signOut }),
    [user, loading, signIn, signUp, signOut]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Import this from hooks/useAuth.js inside components. */
export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuthContext must be used inside <AuthProvider>.');
  }
  return context;
}

export default AuthContext;
