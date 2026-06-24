import { Capacitor } from "@capacitor/core";

const STORAGE_KEY = "zhikuyun.localConnection.v1";

export interface LocalConnection {
  apiBaseUrl: string;
  sessionToken?: string;
}

const isBrowser = () => typeof window !== "undefined";

export const isNativeShell = () => {
  if (!isBrowser()) return false;
  if (Capacitor.isNativePlatform()) return true;
  const protocol = window.location.protocol;
  return (
    protocol === "capacitor:" || protocol === "ionic:" || protocol === "file:"
  );
};

const stripTrailingSlash = (value: string) => value.replace(/\/+$/, "");

export function normalizeLocalApiBaseUrl(input: string): string {
  const raw = input.trim();
  if (!raw) throw new Error("请输入电脑端服务地址");

  const withProtocol = /^[a-z][a-z\d+.-]*:\/\//i.test(raw)
    ? raw
    : `http://${raw}`;
  let parsed: URL;
  try {
    parsed = new URL(withProtocol);
  } catch {
    throw new Error("服务地址格式不正确");
  }

  if (!parsed.hostname) throw new Error("服务地址缺少主机名");
  const port =
    parsed.port === "3000" || parsed.port === "" ? "8000" : parsed.port;
  return stripTrailingSlash(`${parsed.protocol}//${parsed.hostname}:${port}`);
}

export function parseLocalConnectionUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    const api = parsed.searchParams.get("api");
    const host = parsed.searchParams.get("host");
    if (api) return normalizeLocalApiBaseUrl(api);
    if (host) return normalizeLocalApiBaseUrl(host);
  } catch {
    return null;
  }
  return null;
}

export function applyLaunchConnectionFromLocation(): boolean {
  if (!isBrowser()) return false;
  const params = new URLSearchParams(window.location.search);
  const api = params.get("api");
  const host = params.get("host");
  const next = api || host;
  if (!next) return false;
  saveLocalConnection(next);
  return true;
}

export function getSavedLocalConnection(): LocalConnection | null {
  if (!isBrowser()) return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<LocalConnection>;
    if (!parsed.apiBaseUrl) return null;
    return {
      apiBaseUrl: normalizeLocalApiBaseUrl(parsed.apiBaseUrl),
      sessionToken: parsed.sessionToken || undefined,
    };
  } catch {
    return null;
  }
}

export function hasLocalConnection(): boolean {
  return !!getSavedLocalConnection();
}

export function saveLocalConnection(input: string): LocalConnection {
  if (!isBrowser()) throw new Error("当前环境无法保存本地连接");
  const existing = getSavedLocalConnection();
  const next: LocalConnection = {
    apiBaseUrl: normalizeLocalApiBaseUrl(input),
    sessionToken: existing?.sessionToken,
  };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}

export function saveLocalSessionToken(token: string | undefined | null): void {
  if (!isBrowser()) return;
  const existing = getSavedLocalConnection();
  if (!existing) return;
  if (token) {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ ...existing, sessionToken: token }),
    );
    return;
  }
  const withoutToken = { ...existing };
  delete withoutToken.sessionToken;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(withoutToken));
}

export function clearLocalSessionToken(): void {
  saveLocalSessionToken(null);
}

export function clearLocalConnection(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(STORAGE_KEY);
}

export function getLocalAuthHeaders(): Record<string, string> {
  const token = getSavedLocalConnection()?.sessionToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getLocalApiBaseUrl(): string | null {
  if (!isNativeShell()) return null;
  return getSavedLocalConnection()?.apiBaseUrl || null;
}
