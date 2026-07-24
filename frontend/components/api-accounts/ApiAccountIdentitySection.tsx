import { PROVIDER_PRESETS } from "@/lib/providers";
import type { ApiAccountWorkspaceDraft } from "./types";

export default function ApiAccountIdentitySection({
  draft,
  editing,
  saving,
  update,
  selectProvider,
}: {
  draft: ApiAccountWorkspaceDraft;
  editing: boolean;
  saving: boolean;
  update: (fields: Partial<ApiAccountWorkspaceDraft>) => void;
  selectProvider: (provider: string) => void;
}) {
  return (
    <div className="api-account-fields two-columns">
      <label>
        <span>服务商</span>
        <select
          id="api-account-provider"
          className="input"
          aria-label="服务商"
          value={draft.provider}
          disabled={editing || saving}
          onChange={(event) => selectProvider(event.target.value)}
        >
          {PROVIDER_PRESETS.map((item) => (
            <option key={item.provider} value={item.provider}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>显示名称</span>
        <input
          className="input"
          value={draft.displayName}
          onChange={(event) => update({ displayName: event.target.value })}
        />
      </label>
      <label className="wide">
        <span>备注</span>
        <textarea
          aria-label="备注"
          value={draft.notes}
          onChange={(event) => update({ notes: event.target.value })}
        />
      </label>
      <label className="wide">
        <span>官网地址</span>
        <input
          id="api-account-website-url"
          className="input"
          value={draft.websiteUrl}
          onChange={(event) => update({ websiteUrl: event.target.value })}
        />
      </label>
      {editing ? (
        <label className="check">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(event) => update({ enabled: event.target.checked })}
          />
          启用
        </label>
      ) : null}
      <label className="check">
        <input
          type="checkbox"
          checked={draft.isDefault}
          onChange={(event) => update({ isDefault: event.target.checked })}
        />
        设为默认
      </label>
    </div>
  );
}
