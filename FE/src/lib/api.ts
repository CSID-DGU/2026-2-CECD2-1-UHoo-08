import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "./auth";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/$/,
    "",
  ) ?? "";
const AI_API_BASE_URL =
  (import.meta.env.VITE_AI_API_BASE_URL as string | undefined)?.replace(
    /\/$/,
    "",
  ) ?? "";

function getApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  if (AI_API_BASE_URL && path.startsWith("/ai/"))
    return `${AI_API_BASE_URL}${path.replace(/^\/ai/, "")}`;
  if (!API_BASE_URL) return path;
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function readBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

let refreshing: Promise<boolean> | null = null;

function refreshAccessToken(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      const refreshToken = getRefreshToken();
      if (!refreshToken) return false;
      try {
        const res = await fetch(getApiUrl("/auth/token/refresh"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refreshToken }),
        });
        if (!res.ok) return false;
        const body = (await readBody(res)) as {
          data?: { accessToken?: string; refreshToken?: string };
        } | null;
        const access = body?.data?.accessToken;
        if (!access) return false;
        setTokens(access, body?.data?.refreshToken ?? refreshToken);
        return true;
      } catch {
        return false;
      }
    })().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

function expireSession() {
  clearTokens();
  if (window.location.pathname !== "/") window.location.replace("/");
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retried = false,
): Promise<T> {
  const token = getAccessToken();
  const isFormData = options.body instanceof FormData;

  const res = await fetch(getApiUrl(path), {
    ...options,
    headers: {
      // FormData는 Content-Type 자동 설정 (boundary 포함)
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (res.status === 401 && token && !retried && !path.startsWith("/auth/")) {
    if (await refreshAccessToken()) return request<T>(path, options, true);
    expireSession();
  }

  const data = await readBody(res);
  if (!res.ok) throw data;
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  patchForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: "PATCH", body: form }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
