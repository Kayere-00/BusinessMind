import { useEffect, useState } from "react";
import { Download, FileText, Plus, Trash2 } from "lucide-react";
import api, { errMsg, getAccessToken } from "../lib/api";
import type { Dataset, Report } from "../lib/types";
import { useAuth } from "../lib/auth";
import { EmptyState, ErrorBanner, PageHeader, Spinner } from "../components/ui";

export default function Reports() {
  const { user } = useAuth();
  const [reports, setReports] = useState<Report[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ dataset_id: "", title: "" });

  const canCreate = user?.role === "admin" || user?.role === "analyst";

  const load = () => {
    Promise.all([api.get<Report[]>("/reports"), api.get<Dataset[]>("/datasets")])
      .then(([r, d]) => {
        setReports(r.data);
        setDatasets(d.data);
        if (d.data.length) setForm((f) => ({ ...f, dataset_id: f.dataset_id || d.data[0].id }));
      })
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/reports", form);
      setCreating(false);
      setForm((f) => ({ ...f, title: "" }));
      load();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const download = async (report: Report) => {
    try {
      const resp = await api.get(`/reports/${report.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${report.title}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // blob download can fail if token expired mid-flight; fall back to location
      window.open(`/api/reports/${report.id}/download?token=${getAccessToken()}`, "_blank");
    }
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this report?")) return;
    try {
      await api.delete(`/reports/${id}`);
      setReports((r) => r.filter((x) => x.id !== id));
    } catch (err) {
      setError(errMsg(err));
    }
  };

  return (
    <div>
      <PageHeader title="Reports" subtitle="Professional PDF reports generated from your real data.">
        {canCreate && (
          <button className="btn-primary" onClick={() => setCreating((c) => !c)}>
            <Plus size={16} /> New report
          </button>
        )}
      </PageHeader>

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {creating && (
        <form onSubmit={create} className="card mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label className="label" htmlFor="rep-title">Report title</label>
            <input id="rep-title" className="input" required minLength={3} maxLength={200}
                   value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                   placeholder="Q1 Business Review" />
          </div>
          <div>
            <label className="label" htmlFor="rep-ds">Dataset</label>
            <select id="rep-ds" className="input" value={form.dataset_id}
                    onChange={(e) => setForm((f) => ({ ...f, dataset_id: e.target.value }))}>
              {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>
          <div className="flex items-end gap-2">
            <button className="btn-primary" disabled={!form.dataset_id}>Generate PDF</button>
            <button type="button" className="btn-ghost" onClick={() => setCreating(false)}>Cancel</button>
          </div>
        </form>
      )}

      {loading ? <Spinner /> : reports.length === 0 ? (
        <EmptyState title="No reports yet" body="Generate your first PDF report from any dataset — KPIs, insights, breakdowns and forecasts included." />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {reports.map((r) => (
            <div key={r.id} className="card group relative">
              <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-rose-50 text-rose-500 dark:bg-rose-500/10">
                  <FileText size={22} />
                </div>
                <div className="min-w-0">
                  <p className="truncate font-bold">{r.title}</p>
                  <p className="text-xs text-slate-500">
                    {new Date(r.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <button className="btn-ghost !py-2 text-xs" onClick={() => download(r)}>
                  <Download size={14} /> Download PDF
                </button>
                {user?.role === "admin" && (
                  <button className="btn-ghost !py-2 text-xs hover:!bg-rose-50 hover:text-rose-600 dark:hover:!bg-rose-500/10"
                          onClick={() => remove(r.id)}>
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
