import { request } from "./client";
import type {
  VideoNote,
  VideoNoteAiEditRequest,
  VideoNoteAiResponse,
  VideoNoteCreateRequest,
  VideoNoteDetailResponse,
  VideoNoteExportResponse,
  VideoNoteListParams,
  VideoNoteListResponse,
  VideoNoteSaveRequest,
} from "./videoNoteTypes";

export const videoNoteApi = {
  list: ({
    knowledgeBaseId,
    q,
    tag,
    includeBodySearch,
  }: VideoNoteListParams) =>
    request<VideoNoteListResponse>("/video-notes", {
      query: {
        knowledge_base_id: knowledgeBaseId,
        q,
        tag,
        include_body_search: includeBodySearch,
      },
    }),

  detail: (knowledgeBaseId: number, bvid: string) =>
    request<VideoNoteDetailResponse>(`/video-notes/${knowledgeBaseId}/${bvid}`),

  create: (data: VideoNoteCreateRequest) =>
    request<VideoNote>("/video-notes", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  save: (noteId: number, data: VideoNoteSaveRequest) =>
    request<VideoNote>(`/video-notes/${noteId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  exportMarkdown: (noteId: number) =>
    request<VideoNoteExportResponse>(`/video-notes/${noteId}/export/markdown`, {
      method: "POST",
    }),

  generateSummary: (noteId: number) =>
    request<VideoNoteAiResponse>(`/video-notes/${noteId}/generate-summary`, {
      method: "POST",
    }),

  aiEdit: (noteId: number, data: VideoNoteAiEditRequest) =>
    request<VideoNoteAiResponse>(`/video-notes/${noteId}/ai-edit`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
