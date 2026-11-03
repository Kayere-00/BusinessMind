import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BrainCircuit } from "lucide-react";
import { useAuth } from "../lib/auth";
import { errMsg } from "../lib/api";
import { ErrorBanner } from "../components/ui";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center">
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-cyan-400 text-white shadow-card-lg">
            <BrainCircuit size={30} />
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight">BusinessMind AI</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Intelligent Business Intelligence Platform
          </p>
        </div>

        <form onSubmit={submit} className="card space-y-4">
          <h2 className="text-lg font-bold">Welcome back</h2>
          {error && <ErrorBanner message={error} />}
          <div>
            <label className="label" htmlFor="email">Work email</label>
            <input id="email" className="input" type="email" required autoComplete="email"
                   value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
          </div>
          <div>
            <label className="label" htmlFor="password">Password</label>
            <input id="password" className="input" type="password" required autoComplete="current-password"
                   value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••••" />
          </div>
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <p className="text-center text-sm text-slate-500 dark:text-slate-400">
            New to BusinessMind?{" "}
            <Link to="/register" className="font-bold text-brand-600 hover:underline dark:text-brand-400">
              Create your organization
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
