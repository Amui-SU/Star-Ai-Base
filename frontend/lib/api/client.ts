import { getLocalApiBaseUrl, getLocalAuthHeaders } from "@/lib/localConnection";
import { requestWithNativeFallback } from "@/lib/nativeHttp";

const resolveApiBaseUrl = () => {
  const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configuredApiUrl) return configuredApiUrl;
  if (typeof window === "undefined") return "http://localhost:8000";

  const localApiBaseUrl = getLocalApiBaseUrl();
  if (localApiBaseUrl) return localApiBaseUrl;

  const { protocol, hostname } = window.location;
  if (protocol !== "http:" && protocol !== "https:") {
    return "http://localhost:8000";
  }
  return `${protocol}//${hostname}:8000`;
};

export const API_BASE_URL = resolveApiBaseUrl();
export const getApiBaseUrl = resolveApiBaseUrl;

export type RequestOptions = RequestInit & {
  query?: Record<string, string | number | boolean | undefined | null>;
};

function isFormDataBody(body: BodyInit | null | undefined): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

function withQuery(path: string, query?: RequestOptions["query"]): string {
  if (!query) return path;
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      params.set(key, String(value));
    }
  });
  const queryString = params.toString();
  return queryString ? `${path}?${queryString}` : path;
}

export async function request<T>(
  path: string,
  { query, headers, ...init }: RequestOptions = {},
): Promise<T> {
  let response: Response;
  const apiBaseUrl = getApiBaseUrl();
  const isFormData = isFormDataBody(init.body);
  try {
    response = await requestWithNativeFallback(
      `${apiBaseUrl}${withQuery(path, query)}`,
      {
        credentials: "include",
        ...init,
        headers: {
          ...(isFormData ? {} : { "Content-Type": "application/json" }),
          ...getLocalAuthHeaders(),
          ...headers,
        },
      },
    );
  } catch (error) {
    throw new Error(
      `无法连接到后端服务（${apiBaseUrl}）。请确认后端已启动，且接口地址可访问。`,
      { cause: error },
    );
  }

  if (!response.ok) {
    let message = response.statusText || "Request failed";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (
        body.detail &&
        typeof body.detail === "object" &&
        typeof body.detail.message === "string"
      ) {
        message = body.detail.message;
      } else if (typeof body.message === "string") {
        message = body.message;
      }
    } catch {
      // Keep the HTTP status text when the response body is not JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
