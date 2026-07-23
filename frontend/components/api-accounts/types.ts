import type { ApiCredentialEditorTab } from "@/components/api-credentials/ApiCredentialEditorShell";
import type { ThinkingConfig, ThinkingMode } from "@/lib/thinkingConfig";

export type ApiAccountsPanelView = "list" | "create" | "edit";

export interface ApiAccountFormState {
  accountId: number | null;
  provider: string;
  displayName: string;
  apiKey: string;
  baseUrl: string;
  model: string;
  enabled: boolean;
  isDefault: boolean;
  thinkingMode: ThinkingMode;
  thinkingJson: string;
}

export type ThinkingTemplates = Record<string, ThinkingConfig>;

export type ApiAccountEditorTab = ApiCredentialEditorTab;
