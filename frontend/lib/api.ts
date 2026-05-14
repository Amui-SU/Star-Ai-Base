export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

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

export type LLMProvider =
  | "dashscope"
  | "deepseek"
  | "openai"
  | "kimi"
  | "siliconflow"
  | "zhipu"
  | string;

export interface LLMProviderInfo {
  provider: LLMProvider;
  label: string;
  enabled: boolean;
  model: string;
  base_url?: string;
}

export interface LLMConfigResponse {
  current_provider: LLMProvider;
  providers: LLMProviderInfo[];
}

export interface LLMHealthResponse {
  status: "ok" | "down" | string;
  message: string;
  latency_ms: number | null;
  model: string;
  provider?: LLMProvider;
}

export interface ChatResponse {
  answer: string;
  sources: Array<{ bvid: string; title: string; url: string }>;
  thinking?: string | null;
}

interface SaveProviderConfigRequest {
  provider: string;
  api_key: string;
  base_url?: string;
  model?: string;
}

function withSession(path: string, sessionId: string): string {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}session_id=${encodeURIComponent(sessionId)}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = `请求失败 (${response.status})`;
    try {
      const data = await response.json();
      detail = data?.detail || data?.message || detail;
    } catch {
      // Keep the HTTP status fallback when the server did not send JSON.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const authApi = {
  getQRCode: () => request<QRCodeResponse>("/auth/qrcode"),
  pollQRCode: (qrcodeKey: string) =>
    request<LoginStatusResponse>(`/auth/qrcode/poll/${encodeURIComponent(qrcodeKey)}`),
  getSession: (sessionId: string) =>
    request<{ valid: boolean; user_info?: UserInfo }>(
      `/auth/session/${encodeURIComponent(sessionId)}`
    ),
  logout: (sessionId: string) =>
    request<{ message: string }>(`/auth/session/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
    }),
};

export const favoritesApi = {
  getList: (sessionId: string) =>
    request<FavoriteFolder[]>(withSession("/favorites/list", sessionId)),
  getVideos: (mediaId: number, sessionId: string, page = 1, pageSize = 20) =>
    request<{ folder_info: unknown; videos: Video[]; has_more: boolean; page: number; page_size: number }>(
      withSession(
        `/favorites/${mediaId}/videos?page=${page}&page_size=${pageSize}`,
        sessionId
      )
    ),
  getAllVideos: (mediaId: number, sessionId: string) =>
    request<{ total: number; videos: Video[] }>(
      withSession(`/favorites/${mediaId}/all-videos`, sessionId)
    ),
  organizePreview: (folderId: number, sessionId: string) =>
    request<OrganizePreviewResponse>(withSession("/favorites/organize/preview", sessionId), {
      method: "POST",
      body: JSON.stringify({ folder_id: folderId }),
    }),
  organizeExecute: (
    payload: {
      default_folder_id: number;
      moves: Array<{ resource_id: number; resource_type: number; target_folder_id: number }>;
    },
    sessionId: string
  ) =>
    request<{ message: string; moved: number; groups: number }>(
      withSession("/favorites/organize/execute", sessionId),
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    ),
  cleanInvalid: (folderId: number, sessionId: string) =>
    request<{ message: string; data: unknown }>(
      withSession("/favorites/organize/clean-invalid", sessionId),
      {
        method: "POST",
        body: JSON.stringify({ folder_id: folderId }),
      }
    ),
};

export const knowledgeApi = {
  getStats: () => request<KnowledgeStats>("/knowledge/stats"),
  getFolderStatus: (sessionId: string) =>
    request<FolderStatus[]>(withSession("/knowledge/folders/status", sessionId)),
  syncFolders: (payload: { folder_ids?: number[] }, sessionId: string) =>
    request<unknown>(withSession("/knowledge/folders/sync", sessionId), {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  build: (payload: { folder_ids: number[]; exclude_bvids?: string[] }, sessionId: string) =>
    request<{ task_id: string; message: string }>(withSession("/knowledge/build", sessionId), {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getBuildStatus: (taskId: string) =>
    request<BuildStatus>(`/knowledge/build/status/${encodeURIComponent(taskId)}`),
};

export const chatApi = {
  getModelConfig: () => request<LLMConfigResponse>("/chat/llm/config"),
  health: (sessionId: string) =>
    request<LLMHealthResponse>(withSession("/chat/health/llm", sessionId)),
  setModelProvider: (provider: LLMProvider, sessionId: string) =>
    request<{ ok: boolean; current_provider: LLMProvider; model: string; provider_label: string }>(
      withSession("/chat/llm/config", sessionId),
      {
        method: "POST",
        body: JSON.stringify({ provider }),
      }
    ),
  saveModelProviderConfig: (payload: SaveProviderConfigRequest, sessionId: string) =>
    request<{ ok: boolean; current_provider: LLMProvider; model: string; provider_label: string }>(
      withSession("/chat/llm/provider-config", sessionId),
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    ),
  ask: (
    question: string,
    sessionId: string | undefined,
    folderIds?: number[],
    smartSearch = false,
    deepThink = false
  ) =>
    request<ChatResponse>("/chat/ask", {
      method: "POST",
      body: JSON.stringify({
        question,
        session_id: sessionId,
        folder_ids: folderIds,
        smart_search: smartSearch,
        deep_think: deepThink,
      }),
    }),
};
