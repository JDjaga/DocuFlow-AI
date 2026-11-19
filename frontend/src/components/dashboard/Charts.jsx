/**
 * Dashboard charts (Recharts).
 * Every series is real data from GET /api/dashboard/analytics:
 *   - ActivityChart     documents + tasks created per day (last 14 days)
 *   - TaskStatusChart   pending / in review / completed
 *   - PriorityChart     documents grouped by priority
 * When there is no data yet they render a friendly empty state instead of
 * an empty axis.
 */
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { BarChart3, PieChart as PieIcon, TrendingUp } from 'lucide-react';
import EmptyState from '../common/EmptyState';

const INDIGO = '#4f46e5';
const SLATE = '#94a3b8';
const PRIORITY_COLORS = { High: '#e11d48', Medium: '#f59e0b', Low: '#10b981' };
const STATUS_COLORS = { Pending: '#94a3b8', 'In Review': '#f59e0b', Completed: '#10b981' };

const tooltipStyle = {
  borderRadius: 10,
  border: '1px solid #e2e8f0',
  fontSize: 13,
  boxShadow: '0 8px 24px rgba(15, 23, 42, 0.08)',
};

function ChartCard({ title, description, children }) {
  return (
    <section className="card flex h-full flex-col">
      <div className="card-header">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <p className="mt-0.5 text-xs text-slate-500">{description}</p>
        </div>
      </div>
      <div className="flex flex-1 items-center justify-center p-4">{children}</div>
    </section>
  );
}

export function ActivityChart({ data = [] }) {
  const hasData = data.some((point) => point.documents > 0 || point.tasks > 0);

  return (
    <ChartCard title="Document Processing Activity" description="Documents and tasks created per day">
      {hasData ? (
        <ResponsiveContainer width="100%" height={250}>
          <AreaChart data={data} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
            <defs>
              <linearGradient id="documentsFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={INDIGO} stopOpacity={0.25} />
                <stop offset="100%" stopColor={INDIGO} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={40} />
            <Tooltip contentStyle={tooltipStyle} />
            <Area type="monotone" dataKey="documents" name="Documents" stroke={INDIGO} strokeWidth={2} fill="url(#documentsFill)" />
            <Area type="monotone" dataKey="tasks" name="Tasks" stroke={SLATE} strokeWidth={2} fill="transparent" />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState
          icon={TrendingUp}
          title="No activity yet"
          description="Analyze a document and the activity chart will start filling up."
        />
      )}
    </ChartCard>
  );
}

export function TaskStatusChart({ data = [] }) {
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <ChartCard title="Task Status Distribution" description="How your workflow tasks are progressing">
      {total > 0 ? (
        <ResponsiveContainer width="100%" height={250}>
          <PieChart>
            <Pie
              data={data.filter((item) => item.value > 0)}
              dataKey="value"
              nameKey="name"
              innerRadius={55}
              outerRadius={85}
              paddingAngle={3}
              strokeWidth={0}
            >
              {data.map((item) => (
                <Cell key={item.name} fill={STATUS_COLORS[item.name] || INDIGO} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
            <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState
          icon={PieIcon}
          title="No tasks yet"
          description="Create a task or convert AI action items to see this chart."
        />
      )}
    </ChartCard>
  );
}

export function PriorityChart({ data = [] }) {
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <ChartCard title="Document Priority Distribution" description="Your documents grouped by urgency">
      {total > 0 ? (
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} tickLine={false} axisLine={false} />
            <YAxis allowDecimals={0} tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={40} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#f1f5f9' }} />
            <Bar dataKey="value" name="Documents" radius={[6, 6, 0, 0]} maxBarSize={64}>
              {data.map((item) => (
                <Cell key={item.name} fill={PRIORITY_COLORS[item.name] || INDIGO} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState
          icon={BarChart3}
          title="No documents yet"
          description="Documents appear here after your first analysis."
        />
      )}
    </ChartCard>
  );
}
