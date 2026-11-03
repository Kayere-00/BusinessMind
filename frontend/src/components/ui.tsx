import { TrendingDown, TrendingUp } from "lucide-react";

export function KpiCard({
  title, value, sub, delta,
}: { title: string; value: string; sub?: string; delta?: number | null }) {
  const positive = (delta ?? 0) >= 0;
  return (
    <div className="card">
      <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">{title}</p>
      <div className="mt-2 flex items-end justify-between gap-2">
        <p className="text-2xl font-extrabold tracking-tight md:text-[28px]">{value}</p>
        {delta !== undefined && delta !== null && (
          <span
            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold ${
              positive
                ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400"
                : "bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-400"
            }`}
          >
            {positive ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
            {Math.abs(delta).toFixed(1)}%
          </span>
        )}
      </div>
      {sub && <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">{sub}</p>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-10 text-slate-500">
      <div className="h-6 w-6 animate-spin rounded-full border-[3px] border-brand-600 border-t-transparent" />
      {label && <span className="text-sm font-semibold">{label}</span>}
    </div>
  );
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="card flex flex-col items-center py-12 text-center">
      <p className="text-lg font-bold">{title}</p>
      <p className="mt-1 max-w-md text-sm text-slate-500 dark:text-slate-400">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
      {message}
    </div>
  );
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

export function fmt(n: number | null | undefined, currency = false): string {
  if (n === null || n === undefined) return "—";
  return currency
    ? n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 })
    : n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
