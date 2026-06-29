import { request } from "./client";
import type {
  FavoriteFolder,
  LoginStatusResponse,
  OrganizePreviewResponse,
  QRCodeResponse,
  SourceBinding,
  Video,
} from "./sourceTypes";

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
