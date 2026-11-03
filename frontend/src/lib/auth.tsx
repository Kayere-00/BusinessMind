import { createContext, useCallback, useContext, useEffect, useState } from "react";
import api, { clearTokens, getRefreshToken, setTokens } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (org: string, name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState>(null as unknown as AuthState);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const me = await api.get<User>("/auth/me");
      setUser(me.data);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      if (getRefreshToken()) await refreshUser();
      setLoading(false);
    })();
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    const resp = await api.post("/auth/login", { email, password });
    setTokens(resp.data.access_token, resp.data.refresh_token);
    await refreshUser();
  }, [refreshUser]);

  const register = useCallback(
    async (org: string, name: string, email: string, password: string) => {
      const resp = await api.post("/auth/register", {
        org_name: org, full_name: name, email, password,
      });
      setTokens(resp.data.access_token, resp.data.refresh_token);
      await refreshUser();
    },
    [refreshUser]
  );

  const logout = useCallback(async () => {
    const refresh = getRefreshToken();
    try {
      if (refresh) await api.post("/auth/logout", { refresh_token: refresh });
    } finally {
      clearTokens();
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
