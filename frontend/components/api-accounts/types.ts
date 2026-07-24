import type { ApiAccountAdvancedConfig } from "@/lib/apiAccountConfig";
import type { ThinkingConfig, ThinkingMode } from "@/lib/thinkingConfig";

export type ApiAccountsPanelView = "list" | "create" | "edit";
export type ApiAccountSection =
  "identity" | "connection" | "models" | "request" | "json";

export interface ApiAccountWorkspaceDraft {
  accountId: number | null;
  provider: string;
  displayName: string;
  notes: string;
  websiteUrl: string;
  apiKey: string;
  baseUrl: string;
  model: string;
  protocol: string | null;
  authScheme: string | null;
  enabled: boolean;
  isDefault: boolean;
  thinkingMode: ThinkingMode;
  thinkingJson: string;
  advancedConfig: ApiAccountAdvancedConfig;
  modelMappingRows: Array<{ id: string; alias: string; model: string }>;
  headerRows: Array<{ id: string; name: string; value: string }>;
  bodyRaw: string;
}

export type ThinkingTemplates = Record<string, ThinkingConfig>;
