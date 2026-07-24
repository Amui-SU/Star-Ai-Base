export interface ApiAccount {
  id: number;
  provider: string;
  provider_label: string;
  display_name: string;
  base_url: string;
  model: string;
  thinking_config: Record<string, unknown>;
  protocol?: string | null;
  auth_scheme?: string | null;
  website_url?: string | null;
  notes?: string | null;
  advanced_config?: Record<string, unknown>;
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
  protocol?: string | null;
  auth_scheme?: string | null;
  website_url?: string;
  notes?: string;
  advanced_config?: Record<string, unknown>;
  is_default?: boolean;
}

export interface ApiAccountUpdateRequest {
  display_name?: string;
  api_key?: string;
  base_url?: string;
  model?: string;
  thinking_config?: Record<string, unknown>;
  protocol?: string | null;
  auth_scheme?: string | null;
  website_url?: string;
  notes?: string;
  advanced_config?: Record<string, unknown>;
  enabled?: boolean;
  is_default?: boolean;
}

export type ApiAccountDraftValidationStatus =
  | "success"
  | "authentication_failed"
  | "endpoint_unreachable"
  | "timeout"
  | "model_unavailable"
  | "invalid_configuration";

export interface ApiAccountDraftValidationRequest extends Omit<
  ApiAccountCreateRequest,
  "api_key"
> {
  account_id?: number;
  api_key?: string;
}

export interface ApiAccountDraftValidationResponse {
  status: ApiAccountDraftValidationStatus;
  message: string;
  http_status?: number | null;
  section: string;
  latency_ms: number;
}
