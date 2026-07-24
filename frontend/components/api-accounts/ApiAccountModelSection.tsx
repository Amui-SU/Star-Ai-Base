import type { ApiAccountAdvancedConfig } from "@/lib/apiAccountConfig";
import type { ApiAccountWorkspaceDraft } from "./types";

export default function ApiAccountModelSection({
  draft,
  update,
  updateAdvanced,
}: {
  draft: ApiAccountWorkspaceDraft;
  update: (fields: Partial<ApiAccountWorkspaceDraft>) => void;
  updateAdvanced: (fields: Partial<ApiAccountAdvancedConfig>) => void;
}) {
  const rows = draft.modelMappingRows;
  const sync = (next: typeof rows) => {
    update({ modelMappingRows: next });
    const aliases = next.map((row) => row.alias.trim());
    if (
      next.every((row) => row.alias.trim() && row.model.trim()) &&
      new Set(aliases).size === aliases.length
    )
      updateAdvanced({
        model_mapping: Object.fromEntries(
          next.map((row) => [row.alias, row.model]),
        ),
      });
  };
  const replace = (index: number, column: "alias" | "model", value: string) => {
    sync(
      rows.map((item, row) =>
        row === index ? { ...item, [column]: value } : item,
      ),
    );
  };
  return (
    <div className="api-account-model-editor">
      <label className="api-account-field">
        <span>默认模型</span>
        <input
          id="api-account-model"
          className="input"
          value={draft.model}
          onChange={(event) => {
            const model = event.target.value;
            update({ model });
            updateAdvanced({ fallback_model: model });
          }}
        />
      </label>
      <label className="api-account-field">
        <span>兜底模型</span>
        <input
          className="input"
          aria-label="兜底模型"
          value={draft.advancedConfig.fallback_model}
          onChange={(event) =>
            updateAdvanced({ fallback_model: event.target.value })
          }
        />
      </label>
      <div
        id="api-account-model-mapping"
        className="api-account-repeat-list"
        tabIndex={-1}
      >
        {rows.map((item, index) => (
          <div className="api-account-repeat-row" key={item.id}>
            <input
              className="input"
              aria-label={`模型别名 ${index + 1}`}
              value={item.alias}
              onChange={(event) => replace(index, "alias", event.target.value)}
            />
            <span>→</span>
            <input
              className="input"
              aria-label={`真实模型 ID ${index + 1}`}
              value={item.model}
              onChange={(event) => replace(index, "model", event.target.value)}
            />
            <button
              type="button"
              title="删除映射"
              aria-label={`删除模型映射 ${index + 1}`}
              onClick={() => sync(rows.filter((_, row) => row !== index))}
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="btn btn-outline api-account-add-row"
        aria-label="添加模型映射"
        onClick={() =>
          sync([...rows, { id: crypto.randomUUID(), alias: "", model: "" }])
        }
      >
        ＋ 添加映射
      </button>
    </div>
  );
}
