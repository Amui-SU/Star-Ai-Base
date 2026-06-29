import { request } from "./client";
import type {
  BuildStatus,
  FolderStatus,
  KnowledgeStats,
} from "./knowledgeTypes";

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
