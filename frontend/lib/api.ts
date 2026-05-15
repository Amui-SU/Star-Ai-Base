export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface UserInfo {
  mid?: number | string | null;
  uname?: string | null;
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
  user_info?: UserInfo | null;
  session_id?: string | null;
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
}

export interface FavoriteVideosResponse {
  folder_info?: unknown;
  videos: Video[];
  has_more?: boolean;
  page?: number;
  page_size?: number;
  total?: number;
}

export interface BuildRequest {
  folder_ids: number[];
  exclude_bvids?: string[];
}

export interface BuildResponse {
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

export interface KnowledgeStats {
  total_chunks: number;
  total_videos: number;
  collection_name: string;
}

export interface FolderStatus {
  media_id: number;
  indexed_count: number;
  media_count?: number | null;
  last_sync_at?: string | null;
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

export interface OrganizeExecuteRequest {
  default_folder_id: number;
  moves: Array<{
    resource_id: number;
    resource_type: number;
    target_folder_id: number;
  }>;
}

export interface OrganizeExecuteResponse {
  message: string;
  moved: number;
  groups: number;
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

export interface LLMProviderInfo {
  provider: LLMProvider;
  label: string;
  enabled: boolean;
  model: string;
  base_url: string;
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

export interface LLMProviderConfigRequest {
  provider: LLMProvider;
  api_key: string;
  base_url?: string;
  model?: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = `请求失败 (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the status-based fallback for non-JSON errors.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      search.set(key, String(value));
    }
  });
  const text = search.toString();
  return text ? `?${text}` : "";
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
    request<FavoriteFolder[]>(`/favorites/list${query({ session_id: sessionId })}`),
  getVideos: (mediaId: number, sessionId: string, page = 1, pageSize = 20) =>
    request<FavoriteVideosResponse>(
      `/favorites/${mediaId}/videos${query({
        session_id: sessionId,
        page,
        page_size: pageSize,
      })}`,
    ),
  getAllVideos: (mediaId: number, sessionId: string) =>
    request<FavoriteVideosResponse>(
      `/favorites/${mediaId}/all-videos${query({ session_id: sessionId })}`,
    ),
  organizePreview: (folderId: number, sessionId: string) =>
    request<OrganizePreviewResponse>(
      `/favorites/organize/preview${query({ session_id: sessionId })}`,
      {
        method: "POST",
        body: JSON.stringify({ folder_id: folderId }),
      },
    ),
  organizeExecute: (body: OrganizeExecuteRequest, sessionId: string) =>
    request<OrganizeExecuteResponse>(
      `/favorites/organize/execute${query({ session_id: sessionId })}`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
  cleanInvalid: (folderId: number, sessionId: string) =>
    request<{ message: string; data: unknown }>(
      `/favorites/organize/clean-invalid${query({ session_id: sessionId })}`,
      {
        method: "POST",
        body: JSON.stringify({ folder_id: folderId }),
      },
    ),
};

export const knowledgeApi = {
  getStats: () => request<KnowledgeStats>("/knowledge/stats"),
  getFolderStatus: (sessionId: string) =>
    request<FolderStatus[]>(`/knowledge/folders/status${query({ session_id: sessionId })}`),
  build: (body: BuildRequest, sessionId: string) =>
    request<BuildResponse>(`/knowledge/build${query({ session_id: sessionId })}`, {
      method: "POST",
      body: JSON.stringify(body),
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
      body: JSON.stringify({
        question,
        session_id: sessionId,
        folder_ids: folderIds,
        smart_search: smartSearch,
        deep_think: deepThink,
      }),
    }),
  health: () => request<LLMHealthResponse>("/chat/health/llm"),
  getModelConfig: () => request<LLMConfigResponse>("/chat/llm/config"),
  setModelProvider: (provider: LLMProvider) =>
    request<{
      ok: boolean;
      current_provider: LLMProvider;
      model: string;
      provider_label: string;
    }>("/chat/llm/config", {
      method: "POST",
      body: JSON.stringify({ provider }),
    }),
  saveModelProviderConfig: (body: LLMProviderConfigRequest) =>
    request<{
      ok: boolean;
      current_provider: LLMProvider;
      model: string;
      provider_label: string;
    }>("/chat/llm/provider-config", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
