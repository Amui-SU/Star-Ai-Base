import {
  clearLocalSessionToken,
  saveLocalSessionToken,
} from "@/lib/localConnection";

import { getApiBaseUrl, request } from "./client";
import type {
  AdminPasswordResetResponse,
  AdminUser,
  OAuthProvider,
  SystemAuthResponse,
  SystemUser,
} from "./systemAuthTypes";

export const systemAuthApi = {
  getOAuthLoginUrl: (provider: OAuthProvider) => {
    const frontendUrl =
      typeof window === "undefined" ? "" : window.location.origin;
    const params = new URLSearchParams();
    if (frontendUrl) params.set("frontend_url", frontendUrl);
    const query = params.toString();
    return `${getApiBaseUrl()}/system-auth/${provider}/login${query ? `?${query}` : ""}`;
  },

  getGoogleLoginUrl: () => systemAuthApi.getOAuthLoginUrl("google"),

  sendCode: (email: string) =>
    request<{ message: string; code?: string }>("/system-auth/send-code", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  register: async (data: {
    email: string;
    password: string;
    display_name: string;
    code: string;
  }) => {
    const response = await request<SystemAuthResponse>(
      "/system-auth/register",
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    );
    saveLocalSessionToken(response.session_token);
    return response;
  },

  login: async (data: { email: string; password: string }) => {
    const response = await request<SystemAuthResponse>("/system-auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    });
    saveLocalSessionToken(response.session_token);
    return response;
  },

  logout: async () => {
    try {
      return await request<{ ok?: boolean; message?: string }>(
        "/system-auth/logout",
        {
          method: "POST",
        },
      );
    } finally {
      clearLocalSessionToken();
    }
  },

  me: () => request<SystemUser>("/system-auth/me"),

  updateDisplayName: (display_name: string) =>
    request<SystemUser>("/system-auth/me/display-name", {
      method: "PUT",
      body: JSON.stringify({ display_name }),
    }),

  adminListUsers: async () => {
    const response = await request<{ users: AdminUser[] }>(
      "/system-auth/admin/users",
    );
    return response.users;
  },

  adminUpdateUserStatus: (userId: number, status: "active" | "inactive") =>
    request<AdminUser>(`/system-auth/admin/users/${userId}/status`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    }),

  adminResetUserPassword: (userId: number) =>
    request<AdminPasswordResetResponse>(
      `/system-auth/admin/users/${userId}/reset-password`,
      {
        method: "POST",
      },
    ),
};
