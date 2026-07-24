import {
  formatThinkingConfig,
  parseThinkingConfig,
  type ThinkingConfig,
  type ThinkingMode,
} from "@/lib/thinkingConfig";

type ThinkingConfigEditorProps = {
  mode: ThinkingMode;
  customJson: string;
  template: ThinkingConfig;
  error: string;
  onModeChange: (mode: ThinkingMode) => void;
  onCustomJsonChange: (value: string) => void;
  onErrorChange: (error: string) => void;
  disabled?: boolean;
};

const modes: Array<{ value: ThinkingMode; label: string }> = [
  { value: "off", label: "关闭" },
  { value: "standard", label: "标准" },
  { value: "custom", label: "自定义" },
];

export function ThinkingConfigEditor({
  mode,
  customJson,
  template,
  error,
  onModeChange,
  onCustomJsonChange,
  onErrorChange,
  disabled = false,
}: ThinkingConfigEditorProps) {
  const hasStandardTemplate = Object.keys(template).length > 0;

  const formatCustomJson = () => {
    try {
      onCustomJsonChange(formatThinkingConfig(parseThinkingConfig(customJson)));
      onErrorChange("");
    } catch {
      onErrorChange("思考配置 JSON 格式错误");
    }
  };

  return (
    <section className="thinking-config-editor" aria-label="思考配置">
      <div className="thinking-config-editor-modes" aria-label="思考模式">
        {modes.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            aria-pressed={mode === value}
            disabled={
              disabled || (value === "standard" && !hasStandardTemplate)
            }
            onClick={() => onModeChange(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === "standard" ? (
        <label className="thinking-config-editor-json">
          <span>请求体 JSON（标准模板）</span>
          <textarea
            readOnly
            disabled={disabled}
            value={formatThinkingConfig(template)}
            aria-label="请求体 JSON（标准模板）"
          />
        </label>
      ) : null}

      {mode === "custom" ? (
        <div className="thinking-config-editor-custom">
          <label className="thinking-config-editor-json">
            <span>请求体 JSON（自定义）</span>
            <textarea
              value={customJson}
              disabled={disabled}
              aria-label="请求体 JSON（自定义）"
              aria-invalid={Boolean(error)}
              onChange={(event) => onCustomJsonChange(event.target.value)}
            />
          </label>
          <button type="button" disabled={disabled} onClick={formatCustomJson}>
            格式化 JSON
          </button>
        </div>
      ) : null}

      {error ? (
        <p className="thinking-config-editor-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
