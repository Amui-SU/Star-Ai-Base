export type OAuthProvider = "google" | "wechat" | "qq";

export interface SystemUser {
  id: number;
  email: string;
  display_name: string;
  avatar_url?: string;
  status?: string;
  is_admin?: boolean;
}

export interface AdminUser extends SystemUser {
  status: "active" | "inactive" | string;
  is_admin: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AdminPasswordResetResponse {
  user: AdminUser;
  temporary_password: string;
}

export interface Workspace {
  id: number;
  name: string;
  role: string;
}

export interface SystemAuthResponse {
  user: SystemUser;
  workspace: Workspace;
  session_token?: string;
}
