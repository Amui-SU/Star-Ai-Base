import { request } from "./client";
import type {
  LoginStatusResponse,
  QRCodeResponse,
  UserInfo,
} from "./sourceTypes";

export const authApi = {
  getQRCode: () => request<QRCodeResponse>("/auth/qrcode"),

  pollQRCode: (qrcodeKey: string) =>
    request<LoginStatusResponse>(`/auth/qrcode/poll/${qrcodeKey}`),

  getSession: (sessionId: string) =>
    request<{ valid: boolean; user_info?: UserInfo }>(
      `/auth/session/${sessionId}`,
    ),

  logout: (sessionId: string) =>
    request<{ message: string }>(`/auth/session/${sessionId}`, {
      method: "DELETE",
    }),
};
