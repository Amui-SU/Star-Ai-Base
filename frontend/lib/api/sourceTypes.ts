export interface UserInfo {
  mid: number | string;
  uname: string;
  face?: string;
  level?: number;
}

export interface QRCodeResponse {
  qrcode_key: string;
  qrcode_url: string;
  qrcode_image_base64: string;
}

export interface LoginStatusResponse {
  status: "waiting" | "scanned" | "confirmed" | "expired" | string;
  message: string;
  user_info?: UserInfo;
  session_id?: string;
}

export interface SourceBinding {
  id: number;
  source_type: string;
  external_account_id: string;
  external_account_name?: string;
  external_avatar_url?: string;
  status: string;
}

export interface FavoriteFolder {
  media_id: number;
  title: string;
  media_count: number;
  is_selected: boolean;
  is_default?: boolean;
}

export interface Video {
  bvid: string;
  title: string;
  display_title?: string | null;
  original_title?: string | null;
  custom_title?: string | null;
  cover?: string;
  duration?: number;
  owner?: string;
  cid?: number;
}

export interface FavoriteVideosResponse {
  total: number;
  videos: Video[];
}

export interface OrganizePreviewItem {
  bvid: string;
  title: string;
  resource_id: number;
  resource_type: number;
  target_folder_id?: number | null;
  target_folder_title: string;
  reason?: string | null;
}

export interface OrganizePreviewResponse {
  default_folder_id: number;
  default_folder_title: string;
  folders: FavoriteFolder[];
  items: OrganizePreviewItem[];
  stats: Record<string, number>;
}
