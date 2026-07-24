import { ThinkingConfigEditor } from "@/components/api-credentials/ThinkingConfigEditor";
import {
  normalizeApiAccountConfig,
  type ApiAccountAdvancedConfig,
} from "@/lib/apiAccountConfig";
import type { ThinkingConfig } from "@/lib/thinkingConfig";
import type { ApiAccountWorkspaceDraft } from "./types";

export default function ApiAccountRequestSection({
  draft,
  template,
  update,
  updateAdvanced,
}: {
  draft: ApiAccountWorkspaceDraft;
  template: ThinkingConfig;
  update: (fields: Partial<ApiAccountWorkspaceDraft>) => void;
  updateAdvanced: (fields: Partial<ApiAccountAdvancedConfig>) => void;
}) {
  const headerRows = draft.headerRows;
  const syncHeaders = (next: typeof headerRows) => {
    update({ headerRows: next });
    if (next.every((row) => row.name.trim())) {
      try {
        const headers = Object.fromEntries(
          next.map((row) => [row.name, row.value]),
        );
        normalizeApiAccountConfig({ ...draft.advancedConfig, headers });
        updateAdvanced({ headers });
      } catch {
        /* Keep invalid editable rows for local validation. */
      }
    }
  };
  const setHeader = (index: number, column: "name" | "value", value: string) =>
    syncHeaders(
      headerRows.map((item, row) =>
        row === index ? { ...item, [column]: value } : item,
      ),
    );
  return (
    <div className="api-account-request-editor">
      <label className="api-account-field">
        <span>User-Agent</span>
        <input
          className="input"
          value={draft.advancedConfig.user_agent}
          onChange={(event) =>
            updateAdvanced({ user_agent: event.target.value })
          }
        />
      </label>
      <div
        id="api-account-headers"
        className="api-account-subsection"
        tabIndex={-1}
      >
        <h3>Header 覆盖</h3>
        <div className="api-account-repeat-list">
          {headerRows.map((item, index) => (
            <div className="api-account-repeat-row" key={item.id}>
              <input
                className="input"
                aria-label={`Header 名称 ${index + 1}`}
                value={item.name}
                onChange={(event) =>
                  setHeader(index, "name", event.target.value)
                }
              />
              <input
                className="input"
                aria-label={`Header 值 ${index + 1}`}
                value={item.value}
                onChange={(event) =>
                  setHeader(index, "value", event.target.value)
                }
              />
              <button
                type="button"
                title="删除 Header"
                aria-label={`删除 Header ${index + 1}`}
                onClick={() =>
                  syncHeaders(headerRows.filter((_, row) => row !== index))
                }
              >
                ×
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          className="btn btn-outline api-account-add-row"
          aria-label="添加 Header"
          onClick={() =>
            syncHeaders([
              ...headerRows,
              { id: crypto.randomUUID(), name: "", value: "" },
            ])
          }
        >
          ＋ 添加 Header
        </button>
      </div>
      <label className="api-account-field">
        <span>Body 覆盖（JSON 对象）</span>
        <textarea
          aria-label="Body 覆盖 JSON"
          value={draft.bodyRaw}
          onChange={(event) => {
            const bodyRaw = event.target.value;
            update({ bodyRaw });
            try {
              updateAdvanced({ body: JSON.parse(bodyRaw) });
            } catch {
              /* Keep raw text and the last valid object. */
            }
          }}
        />
      </label>
      <div id="api-account-thinking" tabIndex={-1}>
        <ThinkingConfigEditor
          mode={draft.thinkingMode}
          customJson={draft.thinkingJson}
          template={template}
          error=""
          onModeChange={(thinkingMode) => update({ thinkingMode })}
          onCustomJsonChange={(thinkingJson) => update({ thinkingJson })}
          onErrorChange={() => undefined}
        />
      </div>
    </div>
  );
}
