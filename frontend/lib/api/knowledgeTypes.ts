export interface BuildStatus {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  progress: number;
  current_step: string;
  total_videos: number;
  processed_videos: number;
  message: string;
}

export interface FolderStatus {
  media_id: number;
  indexed_count: number;
  media_count?: number;
  last_sync_at?: string | null;
}

export interface KnowledgeStats {
  knowledge_base_id: number;
  workspace_id: number;
  total_videos: number;
  folders: {
    media_id: number;
    indexed_count: number;
    media_count: number;
    last_sync_at: string | null;
  }[];
  scoped: boolean;
}
