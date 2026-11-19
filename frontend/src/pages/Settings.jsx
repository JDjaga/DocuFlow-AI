/**
 * Settings page - account information, AI mode explanation and security notes.
 *
 * What it shows (all real, read from the session and the health API):
 *   - profile: name, email, account created date, user id
 *   - AI mode: Mock vs Gemini with an explanation of what changes
 *   - security: how passwords and tokens are handled (honest notes)
 *   - session: sign out from this device
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound, LogOut, RefreshCw, ShieldCheck, Sparkles, UserRound } from 'lucide-react';
import toast from 'react-hot-toast';
import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import useAuth from '../hooks/useAuth';
import { fetchAiHealth } from '../services/health';
import { getErrorMessage } from '../services/api';
import { formatDateTime, getInitials } from '../utils/formatters';

function Section({ icon: Icon, title, description, children }) {
  return (
    <section className="card p-5">
      <div className="mb-4 flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
          <Icon className="h-[18px] w-[18px]" />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-100 py-3 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="text-sm font-medium text-slate-800">{value}</span>
    </div>
  );
}

export default function Settings() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const [aiInfo, setAiInfo] = useState(null);
  const [aiError, setAiError] = useState('');

  useEffect(() => {
    let active = true;
    fetchAiHealth()
      .then((data) => {
        if (active) setAiInfo(data);
      })
      .catch((error) => {
        if (active) setAiError(getErrorMessage(error));
      });
    return () => {
      active = false;
    };
  }, []);

  function handleLogout() {
    signOut();
    toast.success('Signed out successfully.');
    navigate('/login', { replace: true });
  }

  const isMock = aiInfo?.provider === 'mock';

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Your account, the active AI mode and how this app keeps your data safe."
      />

      <div className="grid gap-5 lg:grid-cols-2">
        {/* -------------------- Profile -------------------- */}
        <Section
          icon={UserRound}
          title="Profile"
          description="Read-only account details from GET /api/auth/me."
        >
          <div className="mb-4 flex items-center gap-4">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-100 text-lg font-semibold text-indigo-700">
              {getInitials(user?.full_name || '?')}
            </span>
            <div className="min-w-0">
              <p className="truncate text-base font-semibold text-slate-900">{user?.full_name}</p>
              <p className="truncate text-sm text-slate-500">{user?.email}</p>
            </div>
          </div>

          <div className="divide-y divide-slate-100">
            <InfoRow label="User ID" value={user?.id ?? '—'} />
            <InfoRow label="Full name" value={user?.full_name || '—'} />
            <InfoRow label="Email address" value={user?.email || '—'} />
            <InfoRow label="Account created" value={formatDateTime(user?.created_at)} />
          </div>

          <p className="mt-4 rounded-lg bg-slate-50 px-3.5 py-2.5 text-xs leading-relaxed text-slate-500">
            Profile editing (name / password change) is intentionally out of scope for this project —
            the API focuses on documents, analysis and workflow tasks.
          </p>
        </Section>

        {/* -------------------- AI mode -------------------- */}
        <Section
          icon={Sparkles}
          title="AI mode"
          description="Which engine analyzes your documents right now."
        >
          {aiError ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {aiError}
            </div>
          ) : !aiInfo ? (
            <p className="text-sm text-slate-500">Loading AI status…</p>
          ) : (
            <>
              <div
                className={`mb-4 rounded-xl border px-4 py-3.5 ${
                  isMock
                    ? 'border-amber-200 bg-amber-50'
                    : 'border-emerald-200 bg-emerald-50'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className={`text-sm font-semibold ${isMock ? 'text-amber-800' : 'text-emerald-800'}`}>
                    {isMock
                      ? '🧪 Mock AI (simulated)'
                      : `✨ ${aiInfo.providers?.[aiInfo.provider]?.label || aiInfo.provider} (real AI)`}
                  </span>
                  <Badge
                    label={aiInfo.status}
                    className={
                      aiInfo.status === 'healthy'
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                        : 'border-amber-200 bg-amber-50 text-amber-700'
                    }
                  />
                </div>
                <p className={`mt-2 text-xs leading-relaxed ${isMock ? 'text-amber-800' : 'text-emerald-800'}`}>
                  {aiInfo.detail}
                </p>
              </div>

              <div className="divide-y divide-slate-100">
                <InfoRow label="Provider" value={aiInfo.provider} />
                <InfoRow label="Mode" value={aiInfo.mode} />
                <InfoRow label="Model" value={aiInfo.model || '—'} />
                <InfoRow
                  label="Provider priority"
                  value={(aiInfo.priority || []).join(' → ') || '—'}
                />
                <InfoRow
                  label="Automatic fallback"
                  value={aiInfo.fallback_enabled ? 'Enabled (transient errors only)' : 'Disabled'}
                />
                <InfoRow
                  label="Embeddings"
                  value={
                    aiInfo.embedding
                      ? `${aiInfo.embedding.provider} · ${aiInfo.embedding.dimension || '?'} dims`
                      : '—'
                  }
                />
                <InfoRow label="API key configured" value={aiInfo.api_key_configured ? 'Yes' : 'No'} />
                <InfoRow label="Request timeout" value={`${aiInfo.timeout_seconds}s`} />
              </div>

              <div className="mt-4 rounded-lg bg-slate-50 px-3.5 py-3 text-xs leading-relaxed text-slate-600">
                <p className="font-semibold text-slate-700">How to switch modes</p>
                <p className="mt-1">
                  Edit <code className="font-mono">backend/.env</code>: set{' '}
                  <code className="font-mono">MOCK_AI=true</code> for the local engine (no key needed), or{' '}
                  <code className="font-mono">MOCK_AI=false</code> and configure{' '}
                  <code className="font-mono">AI_PROVIDER_PRIORITY</code> (e.g.{' '}
                  <code className="font-mono">gemini,openrouter,ollama</code>) with the matching API keys.
                  On rate limits or outages the next provider in the chain is used automatically — Mock is
                  never added silently. See <span className="font-mono">documentation/06_ai_providers.md</span>.
                </p>
              </div>
            </>
          )}
        </Section>

        {/* -------------------- Security -------------------- */}
        <Section
          icon={ShieldCheck}
          title="Security"
          description="How credentials and sessions are handled in this project."
        >
          <ul className="space-y-3">
            {[
              {
                icon: KeyRound,
                title: 'Passwords are hashed with bcrypt',
                text: 'Rounds = 12 with a per-password salt. The plain password is never stored, logged or returned by the API.',
              },
              {
                icon: ShieldCheck,
                title: 'Sessions use signed JWTs (HS256)',
                text: 'Tokens expire after 24 hours (configurable). A tampered or expired token is rejected with 401.',
              },
              {
                icon: UserRound,
                title: 'Every query is scoped to your account',
                text: 'Documents and tasks of other users return 404, so their existence is never revealed.',
              },
              {
                icon: Sparkles,
                title: 'No secrets reach the browser',
                text: 'The health and settings endpoints only return booleans and labels — never API keys or connection strings.',
              },
            ].map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3 rounded-xl border border-slate-100 bg-slate-50/60 px-4 py-3">
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                <div>
                  <p className="text-sm font-medium text-slate-800">{title}</p>
                  <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{text}</p>
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-3 text-xs leading-relaxed text-amber-800">
            <span className="font-semibold">Known trade-off:</span> the JWT is stored in{' '}
            <code className="font-mono">localStorage</code> for simplicity. An httpOnly cookie would be
            safer against XSS but requires CSRF protection — the trade-off is explained in{' '}
            <span className="font-mono">documentation/02</span>.
          </div>
        </Section>

        {/* -------------------- Session -------------------- */}
        <Section
          icon={LogOut}
          title="Session"
          description="Sign out of this device. Your data stays in the database."
        >
          <div className="divide-y divide-slate-100">
            <InfoRow label="Signed in as" value={user?.email || '—'} />
            <InfoRow label="Token storage" value="localStorage (docuflow_token)" />
            <InfoRow label="Auto logout" value="on 401 (expired/invalid token)" />
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button type="button" className="btn-danger" onClick={handleLogout}>
              <LogOut className="h-4 w-4" /> Sign out
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                toast.success('Page reloaded.');
                window.location.reload();
              }}
            >
              <RefreshCw className="h-4 w-4" /> Reload session
            </button>
          </div>
        </Section>
      </div>

      <p className="mt-6 text-center text-xs text-slate-400">
        DocuFlow AI · Turn Documents into Decisions · Port 8001 (backend) / 5173 (frontend)
      </p>
    </div>
  );
}
