import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BrainCircuit } from "lucide-react";
import { useAuth } from "../lib/auth";
import { errMsg } from "../lib/api";
import { ErrorBanner } from "../components/ui";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ org: "", name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register(form.org, form.name, form.email, form.password);
      navigate("/");
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10 dark:bg-slate-950">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center">
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-cyan-400 text-white shadow-card-lg">
            <BrainCircuit size={30} />
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight">Create your workspace</h1>
          <p className="mt-1 text-center text-sm text-slate-500 dark:text-slate-400">
            Your organization gets a fully isolated, private data space.
          </p>
        </div>

        <form onSubmit={submit} className="card space-y-4">
          {error && <ErrorBanner message={error} />}
          <div>
            <label className="label" htmlFor="org">Organization name</label>
            <input id="org" className="input" required minLength={2} maxLength={120}
                   value={form.org} onChange={set("org")} placeholder="Acme Inc." />
          </div>
          <div>
            <label className="label" htmlFor="name">Your full name</label>
            <input id="name" className="input" required minLength={2} maxLength={120}
                   value={form.name} onChange={set("name")} placeholder="Ada Lovelace" />
          </div>
          <div>
            <label className="label" htmlFor="email">Work email</label>
            <input id="email" className="input" type="email" required autoComplete="email"
                   value={form.email} onChange={set("email")} placeholder="you@company.com" />
          </div>
          <div>
            <label className="label" htmlFor="password">Password</label>
            <input id="password" className="input" type="password" required autoComplete="new-password"
                   value={form.password} onChange={set("password")} placeholder="Min. 10 chars, Aa1" />
            <p className="mt-1 text-xs text-slate-500">
              At least 10 characters with uppercase, lowercase and a digit.
            </p>
          </div>
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Creating…" : "Create organization"}
          </button>
          <p className="text-center text-sm text-slate-500 dark:text-slate-400">
            Already have an account?{" "}
            <Link to="/login" className="font-bold text-brand-600 hover:underline dark:text-brand-400">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
