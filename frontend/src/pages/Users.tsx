import { useEffect, useState } from "react";
import { ShieldCheck, UserPlus } from "lucide-react";
import api, { errMsg } from "../lib/api";
import type { User } from "../lib/types";
import { useAuth } from "../lib/auth";
import { ErrorBanner, fmt, PageHeader, Spinner } from "../components/ui";

const ROLES = ["admin", "analyst", "viewer"] as const;

export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [inviting, setInviting] = useState(false);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "viewer" as string });

  const load = () => {
    api.get<User[]>("/users")
      .then((r) => setUsers(r.data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const invite = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/users", form);
      setInviting(false);
      setForm({ full_name: "", email: "", password: "", role: "viewer" });
      load();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const changeRole = async (id: string, role: string) => {
    try {
      await api.patch(`/users/${id}`, { role });
      load();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const toggleActive = async (u: User) => {
    try {
      await api.patch(`/users/${u.id}`, { is_active: !u.is_active });
      load();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  return (
    <div>
      <PageHeader title="Team management" subtitle="Invite colleagues and control their permissions.">
        <button className="btn-primary" onClick={() => setInviting((v) => !v)}>
          <UserPlus size={16} /> Invite member
        </button>
      </PageHeader>

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {inviting && (
        <form onSubmit={invite} className="card mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
          <div>
            <label className="label" htmlFor="u-name">Full name</label>
            <input id="u-name" className="input" required minLength={2} value={form.full_name}
                   onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} />
          </div>
          <div>
            <label className="label" htmlFor="u-email">Email</label>
            <input id="u-email" className="input" type="email" required value={form.email}
                   onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
          </div>
          <div>
            <label className="label" htmlFor="u-pass">Temporary password</label>
            <input id="u-pass" className="input" type="password" required value={form.password}
                   onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} placeholder="Min. 10 chars, Aa1" />
          </div>
          <div>
            <label className="label" htmlFor="u-role">Role</label>
            <select id="u-role" className="input" value={form.role}
                    onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div className="flex items-end gap-2">
            <button className="btn-primary">Invite</button>
            <button type="button" className="btn-ghost" onClick={() => setInviting(false)}>Cancel</button>
          </div>
        </form>
      )}

      {loading ? <Spinner /> : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-700">
                <th className="py-2.5 pr-4">Member</th>
                <th className="py-2.5 pr-4">Role</th>
                <th className="py-2.5 pr-4">Status</th>
                <th className="py-2.5 pr-4">Joined</th>
                <th className="py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-slate-100 dark:border-slate-800">
                  <td className="py-3 pr-4">
                    <p className="font-bold">{u.full_name} {u.id === me?.id && <span className="text-xs text-slate-400">(you)</span>}</p>
                    <p className="text-xs text-slate-500">{u.email}</p>
                  </td>
                  <td className="py-3 pr-4">
                    <select
                      className="input !w-auto !py-1.5 text-xs"
                      value={u.role}
                      disabled={u.id === me?.id}
                      onChange={(e) => changeRole(u.id, e.target.value)}
                      aria-label={`Role for ${u.full_name}`}
                    >
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td className="py-3 pr-4">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                      u.is_active
                        ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
                        : "bg-slate-100 text-slate-500 dark:bg-slate-800"
                    }`}>
                      {u.is_active ? "Active" : "Deactivated"}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-xs text-slate-500">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="py-3">
                    {u.id !== me?.id && (
                      <button className="btn-ghost !py-1.5 text-xs" onClick={() => toggleActive(u)}>
                        <ShieldCheck size={13} /> {u.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-slate-500">
            {fmt(users.length)} members · roles: <b>admin</b> (full control), <b>analyst</b> (upload & analyze), <b>viewer</b> (read-only)
          </p>
        </div>
      )}
    </div>
  );
}
