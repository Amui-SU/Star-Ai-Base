export interface ApiAccount {
  id: number;
  provider: string;
  provider_label: string;
  display_name: string;
  base_url: string;
  model: string;
  thinking_config: Record<string, unknown>;
  enabled: boolean;
  is_default: boolean;
  configured: boolean;
  last_validated_at?: string | null;
  last_error?: string | null;
}

export interface ApiAccountCreateRequest {
  provider: string;
  display_name?: string;
  api_key: string;
  base_url?: string;
  model?: string;
  thinking_config?: Record<string, unknown>;
  is_default?: boolean;
}

export interface ApiAccountUpdateRequest {
  display_name?: string;
  api_key?: string;
  base_url?: string;
  model?: string;
  thinking_config?: Record<string, unknown>;
  enabled?: boolean;
  is_default?: boolean;
}
