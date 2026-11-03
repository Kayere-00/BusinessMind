import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Area, AreaChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Sparkles, UploadCloud } from "lucide-react";
import api, { errMsg } from "../lib/api";
import type { Dataset, Insight, Kpis } from "../lib/types";
import { EmptyState, ErrorBanner, fmt, KpiCard, PageHeader, Spinner } from "../components/ui";

const PIE_COLORS = ["#2563eb", "#22d3ee", "#818cf8", "#34d399", "#fbbf24", "#f472b6", "#a78bfa", "#94a3b8"];

export default function Dashboard() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [series, setSeries] = useState<{ period: string; value: number }[]>([]);
  const [breakdown, setBreakdown] = useState<any>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<Dataset[]>("/datasets").then((r) => {
      setDatasets(r.data);
      if (r.data.length) setSelected(r.data[0].id);
      else setLoading(false);
    }).catch((e) => { setError(errMsg(e)); setLoading(false); });
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError("");
    Promise.all([
      api.get<Kpis>(`/analytics/${selected}/kpis`),
      api.get(`/analytics/${selected}/timeseries`),
      api.get(`/analytics/${selected}/breakdown`),
      api.get<{ insights: Insight[] }>(`/analytics/${selected}/insights`),
    ])
      .then(([k, ts, bd, ins]) => {
        setKpis(k.data);
        setSeries(ts.data?.available ? ts.data.points : []);
        setBreakdown(bd.data?.available ? bd.data : null);
        setInsights(ins.data.insights);
      })
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, [selected]);

  const metricName = kpis?.primary_metric ?? "metric";
  const pieData = useMemo(
    () => (breakdown?.items ?? []).map((i: any) => ({ name: i.label, value: i.value })),
    [breakdown]
  );

  if (!loading && datasets.length === 0) {
    return (
      <EmptyState
        title="No datasets yet"
        body="Upload your first CSV or Excel file and BusinessMind AI will analyze it instantly — KPIs, trends, anomalies and forecasts."
        action={
          <Link to="/datasets" className="btn-primary">
            <UploadCloud size={16} /> Upload a dataset
          </Link>
        }
      />
    );
  }

  return (
    <div>
      <PageHeader title="Dashboard Overview" subtitle="Your business performance at a glance, computed live from your data.">
        <select
          className="input w-auto"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          aria-label="Select dataset"
        >
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
      </PageHeader>

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
      {loading ? <Spinner label="Analyzing your data…" /> : kpis && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard title={`Total ${metricName}`} value={fmt(kpis.metric_total, true)}
                     delta={kpis.growth_first_last_pct ?? undefined}
                     sub={kpis.date_min ? `${kpis.date_min} → ${kpis.date_max}` : undefined} />
            <KpiCard title={`Average ${metricName}`} value={fmt(kpis.metric_mean, true)}
                     sub={`Max ${fmt(kpis.metric_max, true)} · Min ${fmt(kpis.metric_min, true)}`} />
            <KpiCard title="Records analyzed" value={fmt(kpis.row_count)}
                     sub={`${kpis.column_count} columns`} />
            <KpiCard title="Best month" value={kpis.best_month ?? "—"}
                     sub={kpis.worst_month ? `Weakest: ${kpis.worst_month}` : undefined} />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
            <div className="card xl:col-span-2">
              <h3 className="mb-4 text-sm font-bold text-slate-700 dark:text-slate-200">
                Monthly {metricName}
              </h3>
              {series.length ? (
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={series} margin={{ left: 8, right: 8, top: 4 }}>
                    <defs>
                      <linearGradient id="gv" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#2563eb" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#2563eb" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="period" tick={{ fontSize: 11 }} tickLine={false} />
                    <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false}
                           tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`)} />
                    <Tooltip formatter={(v: any) => fmt(Number(v), true)} />
                    <Area type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2.5} fill="url(#gv)" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-12 text-center text-sm text-slate-500">
                  This dataset has no date column, so no time series is available.
                </p>
              )}
            </div>

            <div className="card">
              <h3 className="mb-2 text-sm font-bold text-slate-700 dark:text-slate-200">
                {breakdown ? `${breakdown.metric} by ${breakdown.by}` : "Breakdown"}
              </h3>
              {pieData.length ? (
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={62} outerRadius={95}
                         paddingAngle={3} strokeWidth={0}>
                      {pieData.map((_: any, i: number) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: any) => fmt(Number(v), true)} />
                    <Legend iconSize={9} wrapperStyle={{ fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-12 text-center text-sm text-slate-500">No categorical breakdown available.</p>
              )}
            </div>
          </div>

          <div className="mt-4 rounded-2xl bg-gradient-to-br from-brand-600 via-brand-500 to-cyan-400 p-[1.5px] shadow-card-lg">
            <div className="rounded-2xl bg-white/95 p-5 dark:bg-slate-900/95">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-800 dark:text-slate-100">
                <Sparkles size={16} className="text-brand-600" /> AI Insights — computed from this dataset
              </h3>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {insights.map((ins, i) => (
                  <div key={i} className="rounded-xl bg-slate-50 p-4 dark:bg-slate-800/60">
                    <p className="text-sm font-bold text-brand-700 dark:text-brand-300">{ins.title}</p>
                    <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{ins.body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
