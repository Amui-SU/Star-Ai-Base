import type { ProviderPreset } from "@/lib/providers";
import type { ApiAccountWorkspaceDraft } from "./types";

export default function ApiAccountConnectionSection({
  draft,
  preset,
  editing,
  update,
}: {
  draft: ApiAccountWorkspaceDraft;
  preset: ProviderPreset;
  editing: boolean;
  update: (fields: Partial<ApiAccountWorkspaceDraft>) => void;
}) {
  return (
    <div className="api-account-fields two-columns">
      <label className="wide">
        <span>API Key</span>
        <input
          id="api-account-api-key"
          className="input"
          aria-label="API Key"
          type="password"
          value={draft.apiKey}
          placeholder={editing ? "留空沿用已保存的 Key" : "粘贴 API Key"}
          onChange={(event) => update({ apiKey: event.target.value })}
        />
      </label>
      <label className="wide">
        <span>{preset.kind === "search" ? "服务地址" : "Base URL"}</span>
        <input
          id="api-account-base-url"
          className="input"
          aria-label="Base URL"
          value={draft.baseUrl}
          onChange={(event) => update({ baseUrl: event.target.value })}
        />
      </label>
      {preset.kind === "llm" ? (
        <>
          <label>
            <span>协议</span>
            <select
              className="input"
              aria-label="协议"
              value={draft.protocol ?? ""}
              onChange={(event) => update({ protocol: event.target.value })}
            >
              <option value={preset.protocol ?? ""}>
                {preset.protocol === "anthropic_messages"
                  ? "Anthropic Messages"
                  : "OpenAI Compatible"}
              </option>
            </select>
          </label>
          <label>
            <span>认证方式</span>
            <select
              className="input"
              aria-label="认证方式"
              value={draft.authScheme ?? ""}
              onChange={(event) => update({ authScheme: event.target.value })}
            >
              <option value={preset.authScheme ?? ""}>
                {preset.authScheme === "x_api_key"
                  ? "X-API-Key"
                  : "Bearer Token"}
              </option>
            </select>
          </label>
        </>
      ) : null}
    </div>
  );
}
