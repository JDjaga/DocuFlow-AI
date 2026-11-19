/**
 * Register page - POST /api/auth/register.
 *
 * Client side rules (mirrored by the backend):
 *   - name >= 2 characters
 *   - valid email
 *   - password >= 8 characters
 *   - confirm password must match
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, UserPlus } from 'lucide-react';
import toast from 'react-hot-toast';
import AuthShell from '../components/auth/AuthShell';
import useAuth from '../hooks/useAuth';
import { getErrorMessage } from '../services/api';
import { MIN_PASSWORD_LENGTH, validateRegister } from '../utils/validators';

const EMPTY_FORM = { fullName: '', email: '', password: '', confirmPassword: '' };

export default function Register() {
  const { signUp } = useAuth();
  const navigate = useNavigate();

  const [values, setValues] = useState(EMPTY_FORM);
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

    const validationErrors = validateRegister(values);
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    setSubmitting(true);
    setServerError('');
    try {
      const user = await signUp({
        full_name: values.fullName.trim(),
        email: values.email.trim(),
        password: values.password,
        confirm_password: values.confirmPassword,
      });
      toast.success(`Account created. Welcome, ${user.full_name.split(' ')[0]}!`);
      navigate('/dashboard', { replace: true });
    } catch (error) {
      setServerError(getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Start analyzing documents in under a minute - no credit card required."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-indigo-600 hover:text-indigo-700">
            Sign in
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
          <label className="label" htmlFor="fullName">Full name</label>
          <input
            id="fullName"
            name="fullName"
            type="text"
            autoComplete="name"
            className="input"
            placeholder="Asha Rao"
            value={values.fullName}
            onChange={handleChange}
          />
          {errors.fullName && <p className="mt-1.5 text-xs text-rose-600">{errors.fullName}</p>}
        </div>

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

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="password">Password</label>
            <div className="relative">
              <input
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                className="input !pr-11"
                placeholder={`Min. ${MIN_PASSWORD_LENGTH} characters`}
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

          <div>
            <label className="label" htmlFor="confirmPassword">Confirm password</label>
            <input
              id="confirmPassword"
              name="confirmPassword"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              className="input"
              placeholder="Repeat it"
              value={values.confirmPassword}
              onChange={handleChange}
            />
            {errors.confirmPassword && (
              <p className="mt-1.5 text-xs text-rose-600">{errors.confirmPassword}</p>
            )}
          </div>
        </div>

        <button type="submit" className="btn-primary w-full" disabled={submitting}>
          {submitting ? (
            'Creating account…'
          ) : (
            <>
              <UserPlus className="h-4 w-4" /> Create account
            </>
          )}
        </button>

        <p className="text-center text-xs text-slate-400">
          Passwords must be at least {MIN_PASSWORD_LENGTH} characters long.
        </p>
      </form>
    </AuthShell>
  );
}
