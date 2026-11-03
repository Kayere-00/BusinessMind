import axios, { AxiosError } from "axios";

const api = axios.create({ baseURL: "/api" });

export function getAccessToken() {
  return localStorage.getItem("bm_access");
}
export function getRefreshToken() {
  return localStorage.getItem("bm_refresh");
}
export function setTokens(access: string, refresh: string) {
  localStorage.setItem("bm_access", access);
  localStorage.setItem("bm_refresh", refresh);
}
export function clearTokens() {
  localStorage.removeItem("bm_access");
  localStorage.removeItem("bm_refresh");
}

export async function fetchWithAuth(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const request = (token: string | null) => {
    const headers = new Headers(init.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(input, { ...init, headers });
  };

  let response = await request(getAccessToken());
  if (response.status !== 401) return response;

  refreshing = refreshing ?? tryRefresh();
  const token = await refreshing;
  refreshing = null;
  if (!token) {
    window.location.href = "/login";
    return response;
  }
  response = await request(token);
  if (response.status === 401) window.location.href = "/login";
  return response;
}

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  try {
    const resp = await axios.post("/api/auth/refresh", { refresh_token: refresh });
    setTokens(resp.data.access_token, resp.data.refresh_token);
    return resp.data.access_token;
  } catch {
    clearTokens();
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original: any = error.config;
    const isAuthCall = String(original?.url ?? "").includes("/auth/");
    if (error.response?.status === 401 && !original?._retried && !isAuthCall) {
      original._retried = true;
      refreshing = refreshing ?? tryRefresh();
      const token = await refreshing;
      refreshing = null;
      if (token) {
        original.headers = { ...original.headers, Authorization: `Bearer ${token}` };
        return api(original);
      }
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export function errMsg(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const detail: any = e.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
    return e.message;
  }
  return "Something went wrong.";
}

export default api;
