import { request } from "./client";
import type {
  ChatConversation,
  ChatConversationListResponse,
  ChatConversationSaveRequest,
} from "./chatTypes";

export const chatHistoryApi = {
  list: (params?: { knowledge_base_id?: number | null }) =>
    request<ChatConversationListResponse>("/chat/conversations", {
      query: params,
    }),

  get: (conversationId: number) =>
    request<ChatConversation>(`/chat/conversations/${conversationId}`),

  create: (data: ChatConversationSaveRequest) =>
    request<ChatConversation>("/chat/conversations", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (conversationId: number, data: ChatConversationSaveRequest) =>
    request<ChatConversation>(`/chat/conversations/${conversationId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (conversationId: number) =>
    request<void>(`/chat/conversations/${conversationId}`, {
      method: "DELETE",
    }),
};
