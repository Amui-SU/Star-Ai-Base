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
