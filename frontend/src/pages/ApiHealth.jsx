/**
 * ApiHealth page - live status of every backend component.
 *
 * Data sources (real, polled every 30 seconds):
 *   GET /api/health      -> API + database status, uptime, version
 *   GET /api/health/ai   -> provider chain + availability, embeddings,
 *                           fallback events, real request metrics
 *
 * Rules:
 *   - never render secrets (the backend already hides them, and this
 *     page only displays the fields it expects)
 *   - show a clear healthy / degraded / unavailable badge
 *   - allow a manual refresh for demos and troubleshooting
 */
import { useCallback, useEffect, useState } from 'react';
import { Activity, Database, Network, RefreshCw, Server, Sparkles, Timer, ShieldCheck, Zap } from 'lucide-react';
import toast from 'react-hot-toast';
import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import Loader from '../components/common/Loader';
import { fetchAiHealth, fetchHealth } from '../services/health';
import { getErrorMessage } from '../services/api';

const STATUS_STYLES = {
  healthy: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  degraded: 'border-amber-200 bg-amber-50 text-amber-700',
  unavailable: 'border-rose-200 bg-rose-50 text-rose-700',
};

const STATUS_LABELS = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  unavailable: 'Unavailable',
};

function StatusBadge({ status }) {
  return (
    <Badge
      label={STATUS_LABELS[status] || status}
      className={STATUS_STYLES[status] || 'border-slate-200 bg-slate-100 text-slate-600'}
    />
  );
}

function Panel({ icon: Icon, title, children }) {
  return (
    <section className="card p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
          <Icon className="h-4 w-4" />
        </span>
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function InfoRow({ label, value, mono = false }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-100 py-2.5 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className={`text-sm font-medium text-slate-800 ${mono ? 'font-mono text-xs' : ''}`}>{value}</span>
    </div>
  );
}

const AVAILABILITY_STYLES = {
  true: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  false: 'border-slate-200 bg-slate-100 text-slate-500',
  null: 'border-amber-200 bg-amber-50 text-amber-700',
};

function availabilityBadge(available) {
  const label =
    available === true ? 'Reachable' : available === false ? 'Not reachable' : 'Not checked';
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${AVAILABILITY_STYLES[String(available)]}`}
    >
      {label}
    </span>
  );
}

function formatUptime(seconds = 0) {
  const total = Math.floor(seconds);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;

  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m ${secs}s`;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

export default function ApiHealth() {
  const [health, setHealth] = useState(null);
  const [aiHealth, setAiHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [lastChecked, setLastChecked] = useState(null);

  const load = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError('');

    try {
      // Both checks are independent -> run them together.
      const [healthData, aiData] = await Promise.all([fetchHealth(), fetchAiHealth()]);
      setHealth(healthData);
      setAiHealth(aiData);
      setLastChecked(new Date());
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Auto-refresh every 30 seconds so the page stays truthful.
  useEffect(() => {
    const timer = setInterval(() => load(true), 30000);
    return () => clearInterval(timer);
  }, [load]);

  if (loading) {
    return <Loader label="Checking API health…" />;
  }

  const overall = error ? 'unavailable' : health?.status || 'unavailable';
  const aiStatus = aiHealth?.status || 'unavailable';
  const isMock = aiHealth?.provider === 'mock';

  return (
    <div>
      <PageHeader
        title="API Health"
        description="Live status of the backend, database and AI provider - refreshed every 30 seconds."
        actions={
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              load(true);
              toast.success('Health check refreshed.');
            }}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} /> Refresh now
          </button>
        }
      />

      {/* -------------------- Overall banner -------------------- */}
      <div
        className={`mb-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl border px-5 py-4 ${
          overall === 'healthy'
            ? 'border-emerald-200 bg-emerald-50'
            : overall === 'degraded'
              ? 'border-amber-200 bg-amber-50'
              : 'border-rose-200 bg-rose-50'
        }`}
      >
        <div className="flex items-center gap-3">
          <span
            className={`flex h-11 w-11 items-center justify-center rounded-xl ${
              overall === 'healthy'
                ? 'bg-emerald-100 text-emerald-600'
                : overall === 'degraded'
                  ? 'bg-amber-100 text-amber-600'
                  : 'bg-rose-100 text-rose-600'
            }`}
          >
            <Activity className="h-5 w-5" />
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-900">
              DocuFlow AI is {STATUS_LABELS[overall]?.toLowerCase() || overall}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">
              {lastChecked
                ? `Last checked ${lastChecked.toLocaleTimeString('en-GB')}`
                : 'Not checked yet'}
              {health?.version ? ` · v${health.version}` : ''}
            </p>
          </div>
        </div>
        <StatusBadge status={overall} />
      </div>

      {error && (
        <div className="mb-6 flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <span>⚠️</span>
          <div>
            <p className="font-semibold">Cannot reach the API</p>
            <p className="mt-0.5 text-xs leading-relaxed">
              {error} — start the backend with{' '}
              <code className="rounded bg-rose-100 px-1.5 py-0.5 font-mono text-[11px]">
                python -m uvicorn app.main:app --port 8001
              </code>
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        {/* -------------------- API + database -------------------- */}
        <Panel icon={Server} title="API Service">
          {health ? (
            <>
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm text-slate-500">Overall</span>
                <StatusBadge status={health.status} />
              </div>
              <div className="divide-y divide-slate-100">
                <InfoRow label="Application" value={health.application} />
                <InfoRow label="Version" value={health.version} />
                <InfoRow label="Uptime" value={formatUptime(health.uptime_seconds)} />
                <InfoRow label="Environment" value={health.environment} />
                <InfoRow label="Interactive docs" value={health.endpoints?.docs || '/docs'} mono />
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">No data.</p>
          )}
        </Panel>

        <Panel icon={Database} title="Database">
          {health?.database ? (
            <>
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm text-slate-500">Connection</span>
                <StatusBadge status={health.database.status} />
              </div>
              <p className="text-sm leading-relaxed text-slate-600">{health.database.detail}</p>
              <div className="mt-4 divide-y divide-slate-100">
                <InfoRow
                  label="Checked by"
                  value="SELECT 1 round-trip"
                  mono
                />
                <InfoRow
                  label="Result"
                  value={health.database.status === 'healthy' ? 'Query succeeded' : 'Query failed'}
                />
              </div>
              <p className="mt-4 rounded-lg bg-slate-50 px-3.5 py-2.5 text-xs leading-relaxed text-slate-500">
                Connection strings and credentials are never returned by the health endpoint.
              </p>
            </>
          ) : (
            <p className="text-sm text-slate-500">No data.</p>
          )}
        </Panel>

        {/* -------------------- AI provider -------------------- */}
        <Panel icon={Sparkles} title="AI Provider">
          {aiHealth ? (
            <>
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm text-slate-500">Provider</span>
                <StatusBadge status={aiStatus} />
              </div>
              <div
                className={`mb-3 rounded-xl border px-4 py-3 text-xs leading-relaxed ${
                  isMock
                    ? 'border-amber-200 bg-amber-50 text-amber-800'
                    : 'border-emerald-200 bg-emerald-50 text-emerald-800'
                }`}
              >
                <span className="font-semibold">{isMock ? '🧪 Mock AI mode' : '✨ Real AI mode'}</span>
                <p className="mt-1">
                  {isMock
                    ? 'Analysis runs locally with deterministic rules. No API key, no cost, no network calls.'
                    : `Analysis runs on ${aiHealth.providers?.[aiHealth.provider]?.label || 'the configured provider'} with automatic fallback.`}
                </p>
              </div>
              <div className="divide-y divide-slate-100">
                <InfoRow label="Mode" value={aiHealth.mode} />
                <InfoRow label="Model" value={aiHealth.model || '-'} />
                <InfoRow
                  label="API key configured"
                  value={aiHealth.api_key_configured ? 'Yes' : 'No (not required in Mock mode)'}
                />
                <InfoRow
                  label="Provider priority"
                  value={(aiHealth.priority || []).join(' → ') || '-'}
                  mono
                />
                <InfoRow
                  label="Automatic fallback"
                  value={aiHealth.fallback_enabled ? 'Enabled' : 'Disabled'}
                />
                <InfoRow
                  label="Embeddings"
                  value={
                    aiHealth.embedding
                      ? `${aiHealth.embedding.provider} · ${aiHealth.embedding.dimension || '?'} dims`
                      : '-'
                  }
                  mono
                />
                <InfoRow label="Request timeout" value={`${aiHealth.timeout_seconds}s`} />
                <InfoRow
                  label="Max input length"
                  value={`${(aiHealth.max_input_chars || 0).toLocaleString()} chars`}
                />
              </div>
              <p className="mt-4 flex items-start gap-2 rounded-lg bg-slate-50 px-3.5 py-2.5 text-xs leading-relaxed text-slate-500">
                <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                The API key itself is never sent to the browser or shown on this page.
              </p>
            </>
          ) : (
            <p className="text-sm text-slate-500">No data.</p>
          )}
        </Panel>
      </div>

      {/* -------------------- Provider chain + metrics -------------------- */}
      {aiHealth && (
        <section className="card mt-5 p-5">
          <div className="mb-4 flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
              <Network className="h-4 w-4" />
            </span>
            <h2 className="text-sm font-semibold text-slate-900">AI provider chain</h2>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(aiHealth.providers || {}).map(([name, info]) => {
              const isActive = name === aiHealth.provider;
              return (
                <div
                  key={name}
                  className={`rounded-xl border px-4 py-3 ${
                    isActive
                      ? 'border-emerald-300 bg-emerald-50'
                      : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">
                      {info.label}
                      {isActive && (
                        <span className="ml-1.5 rounded-full bg-emerald-600 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-white">
                          Active
                        </span>
                      )}
                    </p>
                    {availabilityBadge(info.available)}
                  </div>
                  <p className="mt-1.5 font-mono text-[11px] text-slate-600">
                    {info.model || '-'}
                    <span className="text-slate-400">
                      {' '}
                      · {info.inference}
                    </span>
                  </p>
                  <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">{info.detail}</p>
                </div>
              );
            })}
          </div>

          {/* Real counters from the execution log - zeros until first use. */}
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {[
              ['Requests', aiHealth.metrics?.requests],
              ['Success', aiHealth.metrics?.success],
              ['Failed', aiHealth.metrics?.failed],
              ['Fallback events', aiHealth.metrics?.fallback_events],
              ['Avg response', `${Math.round(aiHealth.metrics?.avg_response_time_ms || 0)} ms`],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                  {label}
                </p>
                <p className="mt-1 text-lg font-semibold text-slate-800">{value ?? 0}</p>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-slate-600">
              <Zap className="h-3.5 w-3.5 text-amber-500" /> Recent fallbacks
            </p>
            {(aiHealth.recent_fallbacks || []).length === 0 ? (
              <p className="rounded-lg bg-slate-50 px-3.5 py-2.5 text-xs text-slate-500">
                No automatic fallbacks recorded yet — every request used its primary provider.
              </p>
            ) : (
              <ul className="space-y-2">
                {aiHealth.recent_fallbacks.map((event, index) => (
                  <li
                    key={`${event.at}-${index}`}
                    className="flex flex-wrap items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-800"
                  >
                    <span className="font-mono">{event.from}</span>
                    <span>→</span>
                    <span className="font-semibold">{event.to}</span>
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold">
                      {event.error_category}
                    </span>
                    <span className="ml-auto text-amber-600">{event.at}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}

      {/* -------------------- Endpoint reference -------------------- */}
      <section className="card mt-5 p-5">
        <div className="mb-4 flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
            <Timer className="h-4 w-4" />
          </span>
          <h2 className="text-sm font-semibold text-slate-900">Available endpoints</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(health?.endpoints || {}).map(([name, path]) => (
            <div key={name} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{name}</p>
              <p className="mt-1 font-mono text-xs text-slate-700">{path}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-slate-400">
          Auto-refreshes every 30 seconds. Open{' '}
          <span className="font-mono">http://localhost:8001/docs</span> for the interactive Swagger UI.
        </p>
      </section>
    </div>
  );
}
