import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BarChart3, Bot, BrainCircuit, Database, FileText, LogOut, Moon, Sun, Users as UsersIcon,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";

const NAV = [
  { to: "/", label: "Dashboard", icon: BarChart3Icon(), end: true },
  { to: "/datasets", label: "Datasets", icon: <Database size={18} /> },
  { to: "/assistant", label: "AI Assistant", icon: <Bot size={18} /> },
  { to: "/reports", label: "Reports", icon: <FileText size={18} /> },
];

function BarChart3Icon() {
  return <BarChart3 size={18} />;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { dark, toggle } = useTheme();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 z-20 flex w-60 flex-col border-r border-slate-200 bg-white px-4 py-6 dark:border-slate-800 dark:bg-slate-900 max-md:hidden">
        <div className="mb-8 flex items-center gap-2.5 px-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-cyan-400 text-white">
            <BrainCircuit size={20} />
          </div>
          <div>
            <p className="text-[15px] font-extrabold leading-tight">BusinessMind</p>
            <p className="text-[11px] font-semibold text-brand-600 dark:text-brand-400">AI · BI Platform</p>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${
                  isActive
                    ? "bg-brand-600 text-white shadow-card"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                }`
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
          {user?.role === "admin" && (
            <NavLink
              to="/users"
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${
                  isActive
                    ? "bg-brand-600 text-white shadow-card"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                }`
              }
            >
              <UsersIcon size={18} />
              Team
            </NavLink>
          )}
        </nav>

        <div className="mt-4 rounded-xl bg-slate-50 p-3 dark:bg-slate-800">
          <p className="truncate text-sm font-bold">{user?.full_name}</p>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">
            {user?.org_name} · <span className="font-semibold capitalize text-brand-600 dark:text-brand-400">{user?.role}</span>
          </p>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-h-screen flex-1 flex-col md:pl-60">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/80 px-5 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
          <div className="flex items-center gap-2 font-extrabold md:hidden">
            <BrainCircuit size={20} className="text-brand-600" /> BusinessMind AI
          </div>
          <p className="hidden text-sm font-semibold text-slate-500 dark:text-slate-400 md:block">
            {user?.org_name}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={toggle}
              aria-label="Toggle dark mode"
              className="rounded-xl border border-slate-300 p-2.5 text-slate-600 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500/40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {dark ? <Sun size={17} /> : <Moon size={18} />}
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500/40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              <LogOut size={16} /> <span className="max-sm:hidden">Sign out</span>
            </button>
          </div>
        </header>

        <main className="flex-1 px-5 py-6 lg:px-8">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom nav */}
      <nav className="fixed inset-x-0 bottom-0 z-20 flex justify-around border-t border-slate-200 bg-white py-2 dark:border-slate-800 dark:bg-slate-900 md:hidden">
        {[...NAV, ...(user?.role === "admin" ? [{ to: "/users", label: "Team", icon: <UsersIcon size={20} /> }] : [])].map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-[10px] font-bold ${
                isActive ? "text-brand-600 dark:text-brand-400" : "text-slate-500"
              }`
            }
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
