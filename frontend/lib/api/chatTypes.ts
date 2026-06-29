export interface ChatSource {
  bvid?: string;
  title: string;
  url: string;
  type?: "knowledge" | "web" | string;
}

export interface ChatWebSearchStatus {
  status: "success" | "no_results" | "failed" | string;
  message: string;
  result_count?: number;
  queries?: string[];
  results?: Array<{
    title: string;
    url: string;
    snippet?: string;
  }>;
  errors?: Array<{
    source?: string;
    query?: string;
    url?: string;
    message: string;
  }>;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  thinking?: string;
  web_search?: ChatWebSearchStatus | null;
}

export type WebSearchProvider = "auto" | "tavily" | "html";

export interface ChatConversationScope {
  folder_ids?: number[];
  bvids?: string[];
}

export interface ChatHistoryMessageRequest {
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  sources?: ChatSource[];
  web_search?: ChatWebSearchStatus | null;
}

export interface ChatConversationSaveRequest {
  title?: string;
  workspace_id?: number | null;
  knowledge_base_id?: number | null;
  scope?: ChatConversationScope | null;
  web_search: boolean;
  web_search_provider: WebSearchProvider;
  messages: ChatHistoryMessageRequest[];
}

export interface ChatHistoryMessage extends ChatHistoryMessageRequest {
  id: number;
  sequence: number;
  created_at: string;
}

export interface ChatConversationSummary {
  id: number;
  user_id: number;
  workspace_id?: number | null;
  knowledge_base_id?: number | null;
  title: string;
  scope?: ChatConversationScope | null;
  web_search: boolean;
  web_search_provider: WebSearchProvider;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChatConversation extends ChatConversationSummary {
  messages: ChatHistoryMessage[];
}

export interface ChatConversationListResponse {
  items: ChatConversationSummary[];
}

export interface WebSearchConfigResponse {
  provider: WebSearchProvider;
  tavily_configured: boolean;
  fallback_html: boolean;
  tavily_search_depth: "basic" | "advanced" | string;
}

export type LLMProvider =
  | "dashscope"
  | "deepseek"
  | "openai"
  | "kimi"
  | "qwen"
  | "zhipu"
  | "siliconflow"
  | string;

export type LLMApiSource = "official" | "personal";

export interface LLMProviderInfo {
  provider: string;
  label: string;
  enabled: boolean;
  official_enabled?: boolean;
  personal_enabled?: boolean;
  model: string;
  base_url?: string;
  thinking_config: Record<string, unknown>;
  thinking_template: Record<string, unknown>;
}

export interface LLMConfigResponse {
  current_provider: string;
  current_api_source?: LLMApiSource;
  providers: LLMProviderInfo[];
}

export interface LLMHealthResponse {
  status: "up" | "down" | string;
  message: string;
  latency_ms?: number;
  model: string;
  provider: string;
}
