import { request } from "./client";
import type {
  FavoriteFolder,
  FavoriteVideosResponse,
  OrganizePreviewResponse,
} from "./sourceTypes";

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
