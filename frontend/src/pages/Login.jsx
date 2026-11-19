/**
 * Login page - POST /api/auth/login.
 *
 * Validates locally for instant feedback, then calls the API. On success the
 * token is stored (services/auth.js) and the user lands on the page they
 * originally asked for, or on /dashboard.
 */
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, LogIn, ShieldCheck } from 'lucide-react';
import toast from 'react-hot-toast';
import AuthShell from '../components/auth/AuthShell';
import useAuth from '../hooks/useAuth';
import { getErrorMessage } from '../services/api';
import { validateLogin } from '../utils/validators';

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [values, setValues] = useState({ email: '', password: '' });
  const [errors, setErrors] = useState({});
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState('');

  function handleChange(event) {
    const { name, value } = event.target;
    setValues((previous) => ({ ...previous, [name]: value }));
    setErrors((previous) => ({ ...previous, [name]: '' }));
    setServerError('');
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const validationErrors = validateLogin(values);
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    setSubmitting(true);
    setServerError('');
    try {
      const user = await signIn(values.email.trim(), values.password);
      toast.success(`Welcome back, ${user.full_name.split(' ')[0]}!`);
      navigate(location.state?.from || '/dashboard', { replace: true });
    } catch (error) {
      setServerError(getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Sign in to your workspace"
      subtitle="Enter your credentials to continue to DocuFlow AI."
      footer={
        <>
          Do not have an account?{' '}
          <Link to="/register" className="font-semibold text-indigo-600 hover:text-indigo-700">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        {serverError && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {serverError}
          </div>
        )}

        <div>
          <label className="label" htmlFor="email">Email address</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            className="input"
            placeholder="you@company.com"
            value={values.email}
            onChange={handleChange}
          />
          {errors.email && <p className="mt-1.5 text-xs text-rose-600">{errors.email}</p>}
        </div>

        <div>
          <label className="label" htmlFor="password">Password</label>
          <div className="relative">
            <input
              id="password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              className="input !pr-11"
              placeholder="••••••••"
              value={values.password}
              onChange={handleChange}
            />
            <button
              type="button"
              onClick={() => setShowPassword((value) => !value)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {errors.password && <p className="mt-1.5 text-xs text-rose-600">{errors.password}</p>}
        </div>

        <button type="submit" className="btn-primary w-full" disabled={submitting}>
          {submitting ? (
            'Signing in…'
          ) : (
            <>
              <LogIn className="h-4 w-4" /> Sign in
            </>
          )}
        </button>

        <div className="flex items-start gap-2 rounded-lg border border-slate-200 bg-white px-3.5 py-3 text-xs leading-relaxed text-slate-500">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          <span>
            Your password is hashed with bcrypt and never returned by the API. Sessions use a JWT with a
            24 hour expiry.
          </span>
        </div>
      </form>
    </AuthShell>
  );
}
