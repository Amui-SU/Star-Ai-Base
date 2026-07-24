import { request } from "./client";
import type {
  ApiAccount,
  ApiAccountCreateRequest,
  ApiAccountUpdateRequest,
  ApiAccountDraftValidationRequest,
  ApiAccountDraftValidationResponse,
} from "./apiAccountTypes";

export const apiAccountApi = {
  list: () => request<ApiAccount[]>("/api-accounts"),

  create: (data: ApiAccountCreateRequest) =>
    request<ApiAccount>("/api-accounts", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (accountId: number, data: ApiAccountUpdateRequest) =>
    request<ApiAccount>(`/api-accounts/${accountId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  setDefault: (accountId: number) =>
    request<ApiAccount>(`/api-accounts/${accountId}/set-default`, {
      method: "POST",
    }),

  validate: (accountId: number) =>
    request<ApiAccount>(`/api-accounts/${accountId}/validate`, {
      method: "POST",
    }),

  validateDraft: (data: ApiAccountDraftValidationRequest) =>
    request<ApiAccountDraftValidationResponse>("/api-accounts/validate-draft", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  remove: (accountId: number) =>
    request<void>(`/api-accounts/${accountId}`, {
      method: "DELETE",
    }),
};
