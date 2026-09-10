export interface ImportMethod {
  id: string;
  label: string;
  description: string;
  status: "available" | "coming_soon" | string;
  level: number;
}

export interface ImportUrlResponse {
  ok: boolean;
  status: string;
  source_type: string;
  message: string;
  task_id?: string | null;
  bvid?: string | null;
}

export interface VideoPageInfo {
  cid: number | null;
  page: number;
  part: string;
  duration: number;
}

export interface VideoMultiPartInfo {
  bvid: string;
  title: string;
  is_multi_part: boolean;
  total_parts: number;
  pages: VideoPageInfo[];
  default_cid?: number | null;
  description?: string | null;
  owner_name?: string | null;
  pic_url?: string | null;
}

export interface DetectMultiPartResponse {
  ok: boolean;
  message: string;
  multi_part_info: VideoMultiPartInfo | null;
}

export interface ImportTaskStatus {
  task_id: string;
  status: string;
  progress: number;
  current_step?: string | null;
  message: string;
}

export interface ImportMultiPartResponse {
  ok: boolean;
  message: string;
  bvid?: string | null;
  total_selected: number;
  task_ids: string[];
  import_summary?: string | null;
}
