import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Area, AreaChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { FileDown } from "lucide-react";
import api, { errMsg } from "../lib/api";
import type { Dataset, ForecastResult } from "../lib/types";
import { useAuth } from "../lib/auth";
import { ErrorBanner, fmt, PageHeader, Spinner } from "../components/ui";

export default function DatasetDetail() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [ds, setDs] = useState<Dataset | null>(null);
  const [preview, setPreview] = useState<{ columns: string[]; rows: any[] } | null>(null);
  const [forecast, setForecast] = useState<ForecastResult | null>(null);
  const [periods, setPeriods] = useState(6);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(true);

  const canReport = user?.role === "admin" || user?.role === "analyst";

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.get<Dataset>(`/datasets/${id}`),
      api.get(`/datasets/${id}/preview`, { params: { n: 25 } }),
    ])
      .then(([d, p]) => { setDs(d.data); setPreview(p.data); })
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    api.get<ForecastResult>(`/analytics/${id}/forecast`, { params: { periods } })
      .then((r) => setForecast(r.data))
      .catch(() => setForecast(null));
  }, [id, periods]);

  const forecastChartData = useMemo(() => {
    if (!forecast?.available) return [];
    const hist = (forecast.history ?? []).map((p) => ({ period: p.period, actual: p.value }));
    const fc = (forecast.forecast ?? []).map((p) => ({
      period: p.period, forecast: p.value, lower: p.lower, upper: p.upper,
    }));
    if (hist.length && fc.length) {
      (fc[0] as any).actual = hist[hist.length - 1].actual;
    }
    return [...hist, ...fc];
  }, [forecast]);

  const generateReport = async () => {
    if (!ds) return;
    setMsg("");
    try {
      await api.post("/reports", { dataset_id: ds.id, title: `${ds.name} — Business Report` });
      setMsg("Report generated. Find it under Reports.");
    } catch (e) {
      setMsg(errMsg(e));
    }
  };

  if (loading) return <Spinner label="Loading dataset…" />;
  if (error) return <ErrorBanner message={error} />;
  if (!ds) return null;

  const profile = ds.profile;

  return (
    <div>
      <PageHeader title={ds.name} subtitle={`${ds.original_filename} · ${fmt(ds.row_count)} rows × ${ds.col_count} columns`}>
        {canReport && (
          <button className="btn-primary" onClick={generateReport}>
            <FileDown size={16} /> Generate PDF report
          </button>
        )}
      </PageHeader>
      {msg && <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">{msg}</div>}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="card overflow-x-auto">
          <h3 className="mb-3 text-sm font-bold text-slate-700 dark:text-slate-200">Column profile</h3>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-700">
                <th className="py-2 pr-4">Column</th><th className="py-2 pr-4">Type</th>
                <th className="py-2 pr-4">Nulls</th><th className="py-2 pr-4">Unique</th><th className="py-2">Range / Top</th>
              </tr>
            </thead>
            <tbody>
              {profile?.columns.map((c) => (
                <tr key={c.name} className="border-b border-slate-100 dark:border-slate-800">
                  <td className="py-2 pr-4 font-semibold">{c.name}</td>
                  <td className="py-2 pr-4">
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${
                      c.type === "numeric" ? "bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300"
                      : c.type === "datetime" ? "bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300"
                      : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                    }`}>{c.type}</span>
                  </td>
                  <td className="py-2 pr-4">{c.nulls}</td>
                  <td className="py-2 pr-4">{c.unique}</td>
                  <td className="py-2 text-xs text-slate-500">
                    {c.type === "numeric" && c.min != null && c.max != null
                      ? `${fmt(Number(c.min))} — ${fmt(Number(c.max))}`
                      : c.type === "datetime"
                      ? `${c.min} — ${c.max}`
                      : c.top_values?.slice(0, 2).map((t) => `${t.value} (${t.count})`).join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-700 dark:text-slate-200">
              Forecast {forecast?.metric ? `— ${forecast.metric}` : ""}
            </h3>
            <select className="input w-auto !py-1.5 text-xs" value={periods}
                    onChange={(e) => setPeriods(Number(e.target.value))} aria-label="Forecast horizon">
              {[3, 6, 12].map((p) => <option key={p} value={p}>Next {p} months</option>)}
            </select>
          </div>
          {forecast?.available ? (
            <>
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={forecastChartData} margin={{ left: 8, right: 8, top: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="period" tick={{ fontSize: 10 }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false}
                         tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`)} />
                  <Tooltip formatter={(v: any) => fmt(Number(v), true)} />
                  <Area dataKey="upper" stroke="none" fill="#22d3ee" fillOpacity={0.12} name="Upper bound" />
                  <Line type="monotone" dataKey="actual" stroke="#2563eb" strokeWidth={2.5} dot={false} name="Actual" />
                  <Line type="monotone" dataKey="forecast" stroke="#f59e0b" strokeWidth={2.5}
                        strokeDasharray="6 4" dot={false} name="Forecast" />
                </ComposedChart>
              </ResponsiveContainer>
              <p className="mt-2 text-xs text-slate-500">
                {forecast.model} · MAPE {forecast.mape_pct}% · shaded band = 95% interval
              </p>
            </>
          ) : (
            <p className="py-12 text-center text-sm text-slate-500">
              Forecast unavailable for this dataset (needs a date column and ≥4 months of data).
            </p>
          )}
        </div>
      </div>

      <div className="card mt-4 overflow-x-auto">
        <h3 className="mb-3 text-sm font-bold text-slate-700 dark:text-slate-200">Data preview (first 25 rows)</h3>
        {preview && (
          <table className="w-full min-w-[640px] text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 uppercase text-slate-500 dark:border-slate-700">
                {preview.columns.map((c) => <th key={c} className="whitespace-nowrap py-2 pr-4">{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row, i) => (
                <tr key={i} className="border-b border-slate-100 dark:border-slate-800">
                  {preview.columns.map((c) => (
                    <td key={c} className="whitespace-nowrap py-1.5 pr-4">{String(row[c] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
