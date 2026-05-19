import { STORAGE_KEYS, type StorageAdapter } from "./storage";

// Types are imported from the host app via path alias (@virtus/types).
// This file stays type-agnostic to avoid circular package dependencies —
// the host's tsconfig/babel resolves @virtus/types at build time.

export interface ApiClientOptions {
  baseURL: string;
  apiPrefix?: string;
  storage: StorageAdapter;
  platform?: "web" | "android" | "ios";
  onAuthError?: () => void;
}

type RequestOptions = {
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined>;
  retry?: boolean;
};

export class VirtusApiClient {
  private readonly baseURL: string;
  private readonly apiPrefix: string;
  private readonly storage: StorageAdapter;
  private readonly platform: string;
  private readonly onAuthError?: () => void;
  private isRefreshing = false;
  private refreshPromise: Promise<string | null> | null = null;

  constructor(options: ApiClientOptions) {
    this.baseURL = options.baseURL.replace(/\/$/, "");
    this.apiPrefix = options.apiPrefix ?? "/api/v1";
    this.storage = options.storage;
    this.platform = options.platform ?? "web";
    this.onAuthError = options.onAuthError;
  }

  // ─── Core request ────────────────────────────────────────────────────────

  private async request<T>(
    method: string,
    path: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { body, params, retry = true } = options;

    let url = `${this.baseURL}${this.apiPrefix}${path}`;
    if (params) {
      const defined = Object.fromEntries(
        Object.entries(params)
          .filter(([, v]) => v !== undefined && v !== null)
          .map(([k, v]) => [k, String(v)])
      );
      const qs = new URLSearchParams(defined).toString();
      if (qs) url += `?${qs}`;
    }

    const token = await this.storage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Platform": this.platform,
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401 && retry) {
      const newToken = await this._refreshTokens();
      if (newToken) {
        return this.request<T>(method, path, { ...options, retry: false });
      }
      this.onAuthError?.();
      throw Object.assign(new Error("Sessão expirada. Faça login novamente."), { status: 401 });
    }

    if (!response.ok) {
      let detail = "Erro inesperado. Tente novamente.";
      try {
        const err = await response.json();
        detail = err.detail ?? detail;
      } catch {}
      throw Object.assign(new Error(detail), { status: response.status });
    }

    if (response.status === 204) return undefined as T;
    return response.json();
  }

  // ─── Token refresh ───────────────────────────────────────────────────────

  private async _refreshTokens(): Promise<string | null> {
    if (this.isRefreshing) return this.refreshPromise!;
    this.isRefreshing = true;
    this.refreshPromise = (async () => {
      try {
        const refreshToken = await this.storage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
        if (!refreshToken) throw new Error("no refresh token");

        const data = await this.request<{
          access_token: string;
          refresh_token: string;
        }>("POST", "/auth/refresh", { body: { refresh_token: refreshToken }, retry: false });

        await this.storage.setItem(STORAGE_KEYS.ACCESS_TOKEN, data.access_token);
        await this.storage.setItem(STORAGE_KEYS.REFRESH_TOKEN, data.refresh_token);
        return data.access_token;
      } catch {
        await this.storage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
        await this.storage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
        return null;
      } finally {
        this.isRefreshing = false;
        this.refreshPromise = null;
      }
    })();
    return this.refreshPromise;
  }

  // ─── Generic HTTP verbs ──────────────────────────────────────────────────

  get<T>(path: string, params?: RequestOptions["params"]): Promise<T> {
    return this.request<T>("GET", path, { params });
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("POST", path, { body });
  }

  patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("PATCH", path, { body });
  }

  put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("PUT", path, { body });
  }

  delete<T>(path: string): Promise<T> {
    return this.request<T>("DELETE", path);
  }

  // ─── Auth ────────────────────────────────────────────────────────────────

  async login(email: string, password: string): Promise<void> {
    const data = await this.request<{ access_token: string; refresh_token: string }>(
      "POST", "/auth/login", { body: { email, password } }
    );
    await this.storage.setItem(STORAGE_KEYS.ACCESS_TOKEN, data.access_token);
    await this.storage.setItem(STORAGE_KEYS.REFRESH_TOKEN, data.refresh_token);
  }

  async logout(): Promise<void> {
    const refreshToken = await this.storage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
    if (refreshToken) {
      await this.post("/auth/logout", { refresh_token: refreshToken }).catch(() => {});
    }
    await this.storage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
    await this.storage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
  }

  async isAuthenticated(): Promise<boolean> {
    const token = await this.storage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
    return token !== null;
  }
}
