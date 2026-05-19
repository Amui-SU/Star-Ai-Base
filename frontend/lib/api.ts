export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, ...init } = options;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let message = `请求失败 (${response.status})`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") {
        message = payload.detail;
      }
    } catch {
      const text = await response.text().catch(() => "");
      if (text) message = text;
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

function withSession(path: string, sessionId: string): string {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}session_id=${encodeURIComponent(sessionId)}`;
}

export interface UserInfo {
  mid?: number | string;
  uname: string;
  face?: string | null;
  level?: number | null;
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

export interface SessionInfoResponse {
  valid: boolean;
  user_info?: UserInfo | null;
}

export interface FavoriteFolder {
  media_id: number;
  title: string;
  media_count: number;
  is_selected: boolean;
  is_default?: boolean | null;
}

export interface Video {
  bvid: string;
  title: string;
  cover?: string | null;
  duration?: number | null;
  owner?: string | null;
  play_count?: number | null;
  intro?: string | null;
  cid?: number | null;
  is_selected?: boolean;
}

export interface FavoriteVideosResponse {
  folder_info?: unknown;
  videos: Video[];
  has_more?: boolean;
  page?: number;
  page_size?: number;
}

export interface AllFavoriteVideosResponse {
  total: number;
  videos: Video[];
}

export interface BuildRequest {
  folder_ids: number[];
  exclude_bvids?: string[];
}

export interface BuildStartResponse {
  task_id: string;
  message: string;
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
  media_count?: number | null;
  last_sync_at?: string | null;
}

export interface KnowledgeStats {
  total_chunks: number;
  total_videos: number;
  collection_name: string;
}

export interface ChatResponse {
  answer: string;
  sources: Array<{ bvid: string; title: string; url: string }>;
  thinking?: string | null;
}

export type LLMProvider =
  | "dashscope"
  | "deepseek"
  | "openai"
  | "kimi"
  | "siliconflow"
  | "zhipu"
  | string;

export interface LLMHealthResponse {
  status: "ok" | "down" | string;
  message: string;
  latency_ms: number | null;
  model: string;
  provider?: string;
}

export interface LLMProviderConfig {
  provider: LLMProvider;
  label: string;
  enabled: boolean;
  model: string;
  base_url?: string;
}

export interface LLMConfigResponse {
  current_provider: LLMProvider;
  providers: LLMProviderConfig[];
}

export interface LLMProviderConfigRequest {
  provider: LLMProvider;
  api_key: string;
  base_url?: string;
  model?: string;
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
  stats: {
    total: number;
    matched: number;
    unmatched: number;
    [key: string]: number;
  };
}

export const authApi = {
  getQRCode: () => request<QRCodeResponse>("/auth/qrcode"),
  pollQRCode: (qrcodeKey: string) =>
    request<LoginStatusResponse>(`/auth/qrcode/poll/${encodeURIComponent(qrcodeKey)}`),
  getSession: (sessionId: string) =>
    request<SessionInfoResponse>(`/auth/session/${encodeURIComponent(sessionId)}`),
  logout: (sessionId: string) =>
    request<{ message: string }>(`/auth/session/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
    }),
};

export const favoritesApi = {
  getList: (sessionId: string) =>
    request<FavoriteFolder[]>(withSession("/favorites/list", sessionId)),
  getVideos: (mediaId: number, sessionId: string, page = 1, pageSize = 20) =>
    request<FavoriteVideosResponse>(
      withSession(`/favorites/${mediaId}/videos?page=${page}&page_size=${pageSize}`, sessionId),
    ),
  getAllVideos: (mediaId: number, sessionId: string) =>
    request<AllFavoriteVideosResponse>(
      withSession(`/favorites/${mediaId}/all-videos`, sessionId),
    ),
  organizePreview: (folderId: number, sessionId: string) =>
    request<OrganizePreviewResponse>(withSession("/favorites/organize/preview", sessionId), {
      method: "POST",
      body: { folder_id: folderId },
    }),
  organizeExecute: (
    payload: {
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
      withSession("/favorites/organize/execute", sessionId),
      {
        method: "POST",
        body: payload,
      },
    ),
  cleanInvalid: (folderId: number, sessionId: string) =>
    request<{ message: string; data: unknown }>(
      withSession("/favorites/organize/clean-invalid", sessionId),
      {
        method: "POST",
        body: { folder_id: folderId },
      },
    ),
};

export const knowledgeApi = {
  getStats: () => request<KnowledgeStats>("/knowledge/stats"),
  getFolderStatus: (sessionId: string) =>
    request<FolderStatus[]>(withSession("/knowledge/folders/status", sessionId)),
  build: (payload: BuildRequest, sessionId: string) =>
    request<BuildStartResponse>(withSession("/knowledge/build", sessionId), {
      method: "POST",
      body: payload,
    }),
  getBuildStatus: (taskId: string) =>
    request<BuildStatus>(`/knowledge/build/status/${encodeURIComponent(taskId)}`),
};

export const chatApi = {
  ask: (
    question: string,
    sessionId?: string,
    folderIds?: number[],
    smartSearch = false,
    deepThink = false,
  ) =>
    request<ChatResponse>("/chat/ask", {
      method: "POST",
      body: {
        question,
        session_id: sessionId,
        folder_ids: folderIds,
        smart_search: smartSearch,
        deep_think: deepThink,
      },
    }),
  health: () => request<LLMHealthResponse>("/chat/health/llm"),
  getModelConfig: () => request<LLMConfigResponse>("/chat/llm/config"),
  setModelProvider: (provider: LLMProvider) =>
    request<{ ok: boolean; current_provider: LLMProvider; model: string; provider_label: string }>(
      "/chat/llm/config",
      {
        method: "POST",
        body: { provider },
      },
    ),
  saveModelProviderConfig: (payload: LLMProviderConfigRequest) =>
    request<{ ok: boolean; current_provider: LLMProvider; model: string; provider_label: string }>(
      "/chat/llm/provider-config",
      {
        method: "POST",
        body: payload,
      },
    ),
};
