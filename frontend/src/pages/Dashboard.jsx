/**
 * Dashboard - the first screen after signing in.
 *
 * Data sources (all real, no hardcoded numbers):
 *   hooks/useDashboard.js          -> KPI stats + chart series
 *   services/documents.js          -> 5 most recent documents
 *   services/tasks.js              -> 5 most recent tasks
 */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Activity, ArrowRight, BadgeCheck, CheckCircle2, Clock, FileText, ListChecks, Plus, ScanText, TrendingUp } from 'lucide-react';
import useAuth from '../hooks/useAuth';
import useDashboard from '../hooks/useDashboard';
import { listDocuments } from '../services/documents';
import { listTasks } from '../services/tasks';
import { getErrorMessage } from '../services/api';
import { getGreeting } from '../utils/formatters';
import KpiCard from '../components/dashboard/KpiCard';
import RecentDocuments from '../components/dashboard/RecentDocuments';
import RecentTasks from '../components/dashboard/RecentTasks';
import { ActivityChart, PriorityChart, TaskStatusChart } from '../components/dashboard/Charts';
import Loader from '../components/common/Loader';

export default function Dashboard() {
  const { user } = useAuth();
  const { stats, analytics, loading, error, reload } = useDashboard();

  const [recentDocuments, setRecentDocuments] = useState([]);
  const [recentTasks, setRecentTasks] = useState([]);
  const [recentLoading, setRecentLoading] = useState(true);

  const loadRecent = useCallback(async () => {
    setRecentLoading(true);
    try {
      const [documentsData, tasksData] = await Promise.all([
        listDocuments({ page: 1, page_size: 5, sort: 'newest' }),
        listTasks({ page: 1, page_size: 5 }),
      ]);
      setRecentDocuments(documentsData.items);
      setRecentTasks(tasksData.items);
    } catch (requestError) {
      // Errors are surfaced by the main dashboard error state.
      console.error(getErrorMessage(requestError));
    } finally {
      setRecentLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRecent();
  }, [loadRecent]);

  if (loading) {
    return <Loader label="Loading your workspace…" />;
  }

  const firstName = (user?.full_name || 'there').split(' ')[0];

  return (
    <div className="space-y-6">
      {/* -------------------- Welcome -------------------- */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            {getGreeting()}, {firstName}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Here&apos;s an overview of your document intelligence workspace.
          </p>
        </div>
        <Link to="/analyzer" className="btn-primary self-start sm:self-auto">
          <Plus className="h-4 w-4" /> Analyze Document
        </Link>
      </motion.div>

      {error && (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <span>{error}</span>
          <button type="button" className="font-semibold underline" onClick={reload}>
            Retry
          </button>
        </div>
      )}

      {/* -------------------- KPI cards -------------------- */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          index={0}
          icon={FileText}
          label="Total Documents"
          value={stats?.total_documents ?? 0}
          hint="Documents in your workspace"
          accent="indigo"
        />
        <KpiCard
          index={1}
          icon={BadgeCheck}
          label="Documents Analyzed"
          value={stats?.documents_analyzed ?? 0}
          hint={
            stats?.total_documents
              ? `${Math.round((stats.documents_analyzed / stats.total_documents) * 100)}% analysis success rate`
              : 'Waiting for your first upload'
          }
          accent="emerald"
        />
        <KpiCard
          index={2}
          icon={Clock}
          label="Pending Tasks"
          value={stats?.pending_tasks ?? 0}
          hint={stats?.tasks_due_soon ? `${stats.tasks_due_soon} due within 7 days` : 'Nothing urgent'}
          accent="amber"
        />
        <KpiCard
          index={3}
          icon={CheckCircle2}
          label="Completed Tasks"
          value={stats?.completed_tasks ?? 0}
          hint={`${stats?.task_completion_rate ?? 0}% completion rate`}
          accent="emerald"
        />
      </div>

      {/* -------------------- Charts -------------------- */}
      <div className="grid gap-5 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <ActivityChart data={analytics?.activity || []} />
        </div>
        <div className="lg:col-span-2">
          <TaskStatusChart data={analytics?.task_status || []} />
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <PriorityChart data={analytics?.document_priority || []} />
        </div>
        <div className="lg:col-span-3">
          <RecentDocuments items={recentDocuments} loading={recentLoading} />
        </div>
      </div>

      <RecentTasks items={recentTasks} loading={recentLoading} />

      {/* -------------------- Quick links -------------------- */}
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { to: '/analyzer', icon: ScanText, title: 'Analyze a document', text: 'Upload a PDF/TXT or paste text' },
          { to: '/tasks', icon: ListChecks, title: 'Review tasks', text: 'Move work to in review or done' },
          { to: '/health', icon: Activity, title: 'Check API health', text: 'Backend, database and AI status' },
        ].map(({ to, icon: Icon, title, text }) => (
          <Link key={to} to={to} className="card group flex items-center gap-3 p-4 transition hover:-translate-y-0.5 hover:border-indigo-200">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-500 transition group-hover:bg-indigo-50 group-hover:text-indigo-600">
              <Icon className="h-[18px] w-[18px]" />
            </span>
            <span className="min-w-0">
              <span className="flex items-center gap-1 text-sm font-semibold text-slate-900">
                {title} <ArrowRight className="h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" />
              </span>
              <span className="mt-0.5 block truncate text-xs text-slate-500">{text}</span>
            </span>
          </Link>
        ))}
      </div>

      {/* Small stat row using the same source of truth as the KPI cards. */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-slate-200 bg-white px-5 py-3 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <TrendingUp className="h-3.5 w-3.5 text-indigo-500" />
          {stats?.high_priority_documents ?? 0} high priority documents
        </span>
        <span>{stats?.in_review_tasks ?? 0} tasks in review</span>
        <span>{stats?.total_tasks ?? 0} tasks in total</span>
        {stats?.documents_failed > 0 && (
          <span className="text-rose-600">{stats.documents_failed} failed analyses</span>
        )}
      </div>
    </div>
  );
}
