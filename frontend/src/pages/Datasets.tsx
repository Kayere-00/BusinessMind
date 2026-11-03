import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { FileSpreadsheet, Trash2, UploadCloud } from "lucide-react";
import api, { errMsg } from "../lib/api";
import type { Dataset } from "../lib/types";
import { useAuth } from "../lib/auth";
import { EmptyState, ErrorBanner, fmt, PageHeader, Spinner } from "../components/ui";

export default function Datasets() {
  const { user } = useAuth();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const canUpload = user?.role === "admin" || user?.role === "analyst";

  const load = () => {
    api.get<Dataset[]>("/datasets")
      .then((r) => setDatasets(r.data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const upload = async (file: File) => {
    setBusy(true);
    setError("");
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post("/datasets", fd);
      load();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this dataset permanently?")) return;
    try {
      await api.delete(`/datasets/${id}`);
      setDatasets((d) => d.filter((x) => x.id !== id));
    } catch (e) {
      setError(errMsg(e));
    }
  };

  return (
    <div>
      <PageHeader title="Datasets" subtitle="Upload, validate and manage your organization's data." />

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {canUpload && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f) upload(f);
          }}
          className={`mb-6 flex cursor-pointer flex-col items-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
            dragOver
              ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10"
              : "border-slate-300 bg-white hover:border-brand-400 dark:border-slate-700 dark:bg-slate-900"
          }`}
          onClick={() => fileInput.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && fileInput.current?.click()}
        >
          <UploadCloud size={34} className="mb-2 text-brand-600" />
          <p className="text-sm font-bold">{busy ? "Uploading & validating…" : "Drop a CSV or Excel file here, or click to browse"}</p>
          <p className="mt-1 text-xs text-slate-500">.csv, .xlsx, .xls · max 10 MB · up to 200,000 rows</p>
          <input ref={fileInput} type="file" accept=".csv,.xlsx,.xls" className="hidden"
                 onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </div>
      )}

      {loading ? <Spinner /> : datasets.length === 0 ? (
        <EmptyState title="No datasets" body="Upload your first dataset to unlock dashboards, AI insights and forecasts." />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {datasets.map((d) => (
            <div key={d.id} className="card group relative transition hover:shadow-card-lg">
              <Link to={`/datasets/${d.id}`} className="block">
                <div className="flex items-start gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10">
                    <FileSpreadsheet size={22} />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate font-bold">{d.name}</p>
                    <p className="truncate text-xs text-slate-500">{d.original_filename}</p>
                  </div>
                </div>
                <div className="mt-4 flex gap-4 text-sm">
                  <span><b>{fmt(d.row_count)}</b> rows</span>
                  <span><b>{d.col_count}</b> columns</span>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Added {new Date(d.created_at).toLocaleDateString()}
                </p>
              </Link>
              {user?.role === "admin" && (
                <button
                  onClick={() => remove(d.id)}
                  aria-label={`Delete ${d.name}`}
                  className="absolute right-3 top-3 rounded-lg p-2 text-slate-400 opacity-0 transition hover:bg-rose-50 hover:text-rose-600 focus:opacity-100 group-hover:opacity-100 dark:hover:bg-rose-500/10"
                >
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
