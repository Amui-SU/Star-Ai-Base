import { getApiBaseUrl, request } from "./client";
import type { ChatResponse } from "./chatTypes";
import type {
  KnowledgeBase,
  KnowledgeBaseBuildRequest,
  KnowledgeBaseBuildResponse,
  KnowledgeBaseChatRequest,
  KnowledgeBaseSearchRequest,
  KnowledgeBaseSearchResponse,
  KnowledgeScopeOptions,
} from "./knowledgeBaseTypes";
import type { BuildStatus, KnowledgeStats } from "./knowledgeTypes";

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
    `${getApiBaseUrl()}/knowledge-bases/${knowledgeBaseId}/chat/stream`,

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
    request<{ ok: boolean; deleted_vectors: number }>(
      `/knowledge-bases/${knowledgeBaseId}`,
      { method: "DELETE" },
    ),
};
