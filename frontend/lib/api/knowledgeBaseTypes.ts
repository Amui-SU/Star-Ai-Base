import type { WebSearchProvider } from "./chatTypes";

export interface KnowledgeBase {
  id: number;
  workspace_id: number;
  name: string;
  description?: string;
}

export interface KnowledgeScopeVideo {
  bvid: string;
  title: string;
  original_title?: string | null;
  custom_title?: string | null;
  display_title?: string | null;
}

export interface KnowledgeScopeFolder {
  media_id: number;
  title: string;
  video_count: number;
  videos: KnowledgeScopeVideo[];
}

export interface KnowledgeScopeOptions {
  folders: KnowledgeScopeFolder[];
}

export interface KnowledgeScopeRequest {
  folder_ids?: number[];
  bvids?: string[];
}

export interface KnowledgeBaseSearchRequest extends KnowledgeScopeRequest {
  query: string;
  k?: number;
}

export interface KnowledgeBaseSearchResult {
  content: string;
  bvid?: string | null;
  title?: string | null;
  url?: string | null;
}

export interface KnowledgeBaseSearchResponse {
  results: KnowledgeBaseSearchResult[];
}

export interface KnowledgeBaseChatRequest extends KnowledgeScopeRequest {
  question: string;
  k?: number;
  web_search?: boolean;
  web_search_provider?: WebSearchProvider;
}

export interface KnowledgeBaseBuildRequest {
  source_binding_id: number;
  folder_ids: number[];
  video_folder_ids?: number[];
  bvids?: string[];
  exclude_bvids?: string[];
}

export interface KnowledgeBaseBuildResponse {
  task_id: string;
  status: string;
  workspace_id: number;
  knowledge_base_id: number;
  source_binding_id: number;
}
