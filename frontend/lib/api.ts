const resolveApiBaseUrl = () => {
  const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configuredApiUrl) return configuredApiUrl;
  if (typeof window === "undefined") return "http://localhost:8000";

  const { protocol, hostname } = window.location;
  if (protocol !== "http:" && protocol !== "https:") {
    return "http://localhost:8000";
  }
  return `${protocol}//${hostname}:8000`;
};

export const API_BASE_URL = resolveApiBaseUrl();

export type OAuthProvider = "google" | "wechat" | "qq";

export interface UserInfo {
  mid: number | string;
  uname: string;
  face?: string;
  level?: number;
}

export interface QRCodeResponse {
  qrcode_key: string;
  qrcode_url: string;
  qrcode_image_base64: string;
}

export interface LoginStatusResponse {
  status: "waiting" | "scanned" | "confirmed" | "expired" | string;
  message: string;
  user_info?: UserInfo;
  session_id?: string;
}

export interface SystemUser {
  id: number;
  email: string;
  display_name: string;
  avatar_url?: string;
}

export interface Workspace {
  id: number;
  name: string;
  role: string;
}

export interface SystemAuthResponse {
  user: SystemUser;
  workspace: Workspace;
}

export interface SourceBinding {
  id: number;
  source_type: string;
  external_account_id: string;
  external_account_name?: string;
  external_avatar_url?: string;
  status: string;
}

export interface KnowledgeBase {
  id: number;
  workspace_id: number;
  name: string;
  description?: string;
}

export interface KnowledgeScopeVideo {
  bvid: string;
  title: string;
  original_title?: string | null;
  custom_title?: string | null;
  display_title?: string | null;
}

export interface KnowledgeScopeFolder {
  media_id: number;
  title: string;
  video_count: number;
  videos: KnowledgeScopeVideo[];
}

export interface KnowledgeScopeOptions {
  folders: KnowledgeScopeFolder[];
}

export interface KnowledgeScopeRequest {
  folder_ids?: number[];
  bvids?: string[];
}

export interface KnowledgeBaseSearchRequest extends KnowledgeScopeRequest {
  query: string;
  k?: number;
}

export interface KnowledgeBaseSearchResult {
  content: string;
  bvid?: string | null;
  title?: string | null;
  url?: string | null;
}

export interface KnowledgeBaseSearchResponse {
  results: KnowledgeBaseSearchResult[];
}

export interface KnowledgeBaseChatRequest extends KnowledgeScopeRequest {
  question: string;
  k?: number;
}

export interface KnowledgeBaseBuildRequest {
  source_binding_id: number;
  folder_ids: number[];
  exclude_bvids?: string[];
}

export interface KnowledgeBaseBuildResponse {
  task_id: string;
  status: string;
  workspace_id: number;
  knowledge_base_id: number;
  source_binding_id: number;
}

export interface FavoriteFolder {
  media_id: number;
  title: string;
  media_count: number;
  is_selected: boolean;
  is_default?: boolean;
}

export interface Video {
  bvid: string;
  title: string;
  display_title?: string | null;
  original_title?: string | null;
  custom_title?: string | null;
  cover?: string;
  duration?: number;
  owner?: string;
  cid?: number;
}

export interface FavoriteVideosResponse {
  total: number;
  videos: Video[];
}

export interface BuildStatus {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  progress: number;
  current_step: string;
  total_videos: number;
  processed_videos: number;
  message: string;
}

export interface FolderStatus {
  media_id: number;
  indexed_count: number;
  media_count?: number;
  last_sync_at?: string | null;
}

export interface KnowledgeStats {
  knowledge_base_id: number;
  workspace_id: number;
  total_videos: number;
  folders: {
    media_id: number;
    indexed_count: number;
    media_count: number;
    last_sync_at: string | null;
  }[];
  scoped: boolean;
}

export interface OrganizePreviewItem {
  bvid: string;
  title: string;
  resource_id: number;
  resource_type: number;
  target_folder_id?: number | null;
  target_folder_title: string;
  reason?: string | null;
}

export interface OrganizePreviewResponse {
  default_folder_id: number;
  default_folder_title: string;
  folders: FavoriteFolder[];
  items: OrganizePreviewItem[];
  stats: Record<string, number>;
}

export interface ChatSource {
  bvid: string;
  title: string;
  url: string;
}

export interface ImportMethod {
  id: string;
  label: string;
  description: string;
  status: "available" | "coming_soon" | string;
  level: number;
}

export interface ImportUrlResponse {
  ok: boolean;
  status: string;
  source_type: string;
  message: string;
  task_id?: string | null;
  bvid?: string | null;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  thinking?: string;
}

export type LLMProvider =
  | "dashscope"
  | "deepseek"
  | "openai"
  | "kimi"
  | "qwen"
  | "zhipu"
  | "siliconflow"
  | string;

export interface LLMProviderInfo {
  provider: string;
  label: string;
  enabled: boolean;
  model: string;
  base_url?: string;
  thinking_config: Record<string, unknown>;
  thinking_template: Record<string, unknown>;
}

export interface LLMConfigResponse {
  current_provider: string;
  providers: LLMProviderInfo[];
}

export interface LLMHealthResponse {
  status: "up" | "down" | string;
  message: string;
  latency_ms?: number;
  model: string;
  provider: string;
}

type RequestOptions = RequestInit & {
  query?: Record<string, string | number | boolean | undefined | null>;
};

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
  try {
    response = await fetch(`${API_BASE_URL}${withQuery(path, query)}`, {
      credentials: "include",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
    });
  } catch (error) {
    throw new Error(
      `无法连接到后端服务（${API_BASE_URL}）。请确认后端已启动，且接口地址可访问。`,
      { cause: error },
    );
  }

  if (!response.ok) {
    let message = response.statusText || "Request failed";
    try {
      const body = await response.json();
      message = body.detail || body.message || message;
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

export const systemAuthApi = {
  getOAuthLoginUrl: (provider: OAuthProvider) => {
    const frontendUrl =
      typeof window === "undefined" ? "" : window.location.origin;
    const params = new URLSearchParams();
    if (frontendUrl) params.set("frontend_url", frontendUrl);
    const query = params.toString();
    return `${API_BASE_URL}/system-auth/${provider}/login${query ? `?${query}` : ""}`;
  },

  getGoogleLoginUrl: () => systemAuthApi.getOAuthLoginUrl("google"),

  sendCode: (email: string) =>
    request<{ message: string; code?: string }>("/system-auth/send-code", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  register: (data: {
    email: string;
    password: string;
    display_name: string;
    code: string;
  }) =>
    request<SystemAuthResponse>("/system-auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  login: (data: { email: string; password: string }) =>
    request<SystemAuthResponse>("/system-auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  logout: () =>
    request<{ ok?: boolean; message?: string }>("/system-auth/logout", {
      method: "POST",
    }),

  me: () => request<SystemUser>("/system-auth/me"),

  updateDisplayName: (display_name: string) =>
    request<SystemUser>("/system-auth/me/display-name", {
      method: "PUT",
      body: JSON.stringify({ display_name }),
    }),
};

export const sourceBindingApi = {
  list: () => request<SourceBinding[]>("/source-bindings"),

  revoke: (bindingId: number) =>
    request<{ ok: boolean }>(`/source-bindings/${bindingId}`, {
      method: "DELETE",
    }),

  getBilibiliQRCode: () =>
    request<QRCodeResponse>("/source-bindings/bilibili/qrcode"),

  pollBilibiliQRCode: (qrcodeKey: string) =>
    request<LoginStatusResponse>(
      `/source-bindings/bilibili/qrcode/poll/${qrcodeKey}`,
    ),

  // 通过绑定获取收藏夹（替代旧 favoritesApi）
  getFavorites: (bindingId: number) =>
    request<FavoriteFolder[]>(`/source-bindings/${bindingId}/favorites`),

  getFavoriteVideos: (
    bindingId: number,
    mediaId: number,
    knowledgeBaseId?: number | null,
    page = 1,
    pageSize = 20,
  ) =>
    request<{
      folder_info: Record<string, unknown>;
      videos: Video[];
      has_more: boolean;
      page: number;
      page_size: number;
    }>(
      `/source-bindings/${bindingId}/favorites/${mediaId}/videos?page=${page}&page_size=${pageSize}${
        knowledgeBaseId ? `&knowledge_base_id=${knowledgeBaseId}` : ""
      }`,
    ),

  getAllFavoriteVideos: (
    bindingId: number,
    mediaId: number,
    knowledgeBaseId?: number | null,
  ) =>
    request<{ total: number; valid: number; videos: Video[] }>(
      `/source-bindings/${bindingId}/favorites/${mediaId}/all-videos${
        knowledgeBaseId ? `?knowledge_base_id=${knowledgeBaseId}` : ""
      }`,
    ),

  updateVideoTitle: (
    bindingId: number,
    data: { bvid: string; title?: string | null; knowledge_base_id: number },
  ) =>
    request<{ ok: boolean; bvid: string; custom_title?: string | null }>(
      `/source-bindings/${bindingId}/videos/title`,
      { method: "PUT", body: JSON.stringify(data) },
    ),

  organizePreview: (bindingId: number, folderId: number) =>
    request<OrganizePreviewResponse>(
      `/source-bindings/${bindingId}/favorites/organize-preview?folder_id=${folderId}`,
    ),

  cleanInvalid: (bindingId: number, folderId: number) =>
    request<{ ok: boolean }>(
      `/source-bindings/${bindingId}/favorites/${folderId}/clean-invalid`,
      { method: "POST" },
    ),

  organizeExecute: (
    bindingId: number,
    data: {
      default_folder_id: number;
      moves: {
        resource_id: number;
        resource_type: number;
        target_folder_id: number;
      }[];
    },
  ) =>
    request<{ message: string; moved: number; groups: number }>(
      `/source-bindings/${bindingId}/favorites/organize-execute`,
      { method: "POST", body: JSON.stringify(data) },
    ),
};

export const knowledgeBaseApi = {
  list: () => request<KnowledgeBase[]>("/knowledge-bases"),

  create: (data: { name: string; description?: string }) =>
    request<KnowledgeBase>("/knowledge-bases", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  stats: (knowledgeBaseId: number) =>
    request<KnowledgeStats>(`/knowledge-bases/${knowledgeBaseId}/stats`),

  getScopeOptions: (knowledgeBaseId: number) =>
    request<KnowledgeScopeOptions>(
      `/knowledge-bases/${knowledgeBaseId}/scope-options`,
    ),

  search: (knowledgeBaseId: number, data: KnowledgeBaseSearchRequest) =>
    request<KnowledgeBaseSearchResponse>(
      `/knowledge-bases/${knowledgeBaseId}/search`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    ),

  chat: (knowledgeBaseId: number, data: KnowledgeBaseChatRequest) =>
    request<ChatResponse>(`/knowledge-bases/${knowledgeBaseId}/chat`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  chatStreamUrl: (knowledgeBaseId: number) =>
    `${API_BASE_URL}/knowledge-bases/${knowledgeBaseId}/chat/stream`,

  build: (knowledgeBaseId: number, data: KnowledgeBaseBuildRequest) =>
    request<KnowledgeBaseBuildResponse>(
      `/knowledge-bases/${knowledgeBaseId}/build`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    ),

  getBuildStatus: (knowledgeBaseId: number, taskId: string) =>
    request<BuildStatus>(
      `/knowledge-bases/${knowledgeBaseId}/build/status/${taskId}`,
    ),

  delete: (knowledgeBaseId: number) =>
    request<{ ok: boolean; deleted_vectors: number; warning?: string }>(
      `/knowledge-bases/${knowledgeBaseId}`,
      { method: "DELETE" },
    ),
};

export const importApi = {
  methods: () => request<{ methods: ImportMethod[] }>("/imports/methods"),

  importUrl: (data: {
    url: string;
    source_type?: string;
    knowledge_base_id?: number | null;
  }) =>
    request<ImportUrlResponse>("/imports/url", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export const authApi = {
  getQRCode: () => request<QRCodeResponse>("/auth/qrcode"),

  pollQRCode: (qrcodeKey: string) =>
    request<LoginStatusResponse>(`/auth/qrcode/poll/${qrcodeKey}`),

  getSession: (sessionId: string) =>
    request<{ valid: boolean; user_info?: UserInfo }>(
      `/auth/session/${sessionId}`,
    ),

  logout: (sessionId: string) =>
    request<{ message: string }>(`/auth/session/${sessionId}`, {
      method: "DELETE",
    }),
};

export const favoritesApi = {
  getList: (sessionId: string) =>
    request<FavoriteFolder[]>("/favorites/list", {
      query: { session_id: sessionId },
    }),

  getAllVideos: (mediaId: number, sessionId: string) =>
    request<FavoriteVideosResponse>(`/favorites/${mediaId}/all-videos`, {
      query: { session_id: sessionId },
    }),

  organizePreview: (folderId: number, sessionId: string) =>
    request<OrganizePreviewResponse>("/favorites/organize/preview", {
      method: "POST",
      query: { session_id: sessionId },
      body: JSON.stringify({ folder_id: folderId }),
    }),

  organizeExecute: (
    data: {
      default_folder_id: number;
      moves: Array<{
        resource_id: number;
        resource_type: number;
        target_folder_id: number;
      }>;
    },
    sessionId: string,
  ) =>
    request<{ message: string; moved: number; groups: number }>(
      "/favorites/organize/execute",
      {
        method: "POST",
        query: { session_id: sessionId },
        body: JSON.stringify(data),
      },
    ),

  cleanInvalid: (folderId: number, sessionId: string) =>
    request<{ message: string; data: unknown }>(
      "/favorites/organize/clean-invalid",
      {
        method: "POST",
        query: { session_id: sessionId },
        body: JSON.stringify({ folder_id: folderId }),
      },
    ),
};

export const knowledgeApi = {
  getStats: () => request<KnowledgeStats>("/knowledge/stats"),

  getFolderStatus: (sessionId: string) =>
    request<FolderStatus[]>("/knowledge/folders/status", {
      query: { session_id: sessionId },
    }),

  build: (
    data: { folder_ids: number[]; exclude_bvids?: string[] },
    sessionId: string,
  ) =>
    request<{ task_id: string; message?: string }>("/knowledge/build", {
      method: "POST",
      query: { session_id: sessionId },
      body: JSON.stringify(data),
    }),

  getBuildStatus: (taskId: string) =>
    request<BuildStatus>(`/knowledge/build/status/${taskId}`),
};

export const chatApi = {
  ask: (question: string, sessionId?: string | null, folderIds?: number[]) =>
    request<ChatResponse>("/chat/ask", {
      method: "POST",
      body: JSON.stringify({
        question,
        session_id: sessionId,
        folder_ids: folderIds,
      }),
    }),

  getModelConfig: () => request<LLMConfigResponse>("/chat/llm/config"),

  setModelProvider: (provider: LLMProvider) =>
    request<{ ok: boolean; current_provider: string; model: string }>(
      "/chat/llm/config",
      {
        method: "POST",
        body: JSON.stringify({ provider }),
      },
    ),

  saveModelProviderConfig: (data: {
    provider: string;
    api_key?: string;
    base_url?: string;
    model?: string;
    thinking_mode: "off" | "standard" | "custom";
    thinking_config?: Record<string, unknown>;
  }) =>
    request<{
      ok: boolean;
      current_provider: string;
      model: string;
      provider_label: string;
      thinking_config: Record<string, unknown>;
      thinking_template: Record<string, unknown>;
      verified: boolean;
      latency_ms: number;
    }>("/chat/llm/provider-config", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  health: () => request<LLMHealthResponse>("/chat/health/llm"),
};
