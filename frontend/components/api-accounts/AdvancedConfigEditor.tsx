import { useRef, useState } from "react";
import { useDialogFocusTrap } from "@/components/ui/useDialogFocusTrap";

export default function AdvancedConfigEditor({
  raw,
  error,
  disabled,
  onRawChange,
  onApply,
}: {
  raw: string;
  error: string;
  disabled: boolean;
  onRawChange: (raw: string) => void;
  onApply: (raw?: string) => boolean;
}) {
  const [focused, setFocused] = useState(false);
  const [focusRaw, setFocusRaw] = useState("");
  const [focusError, setFocusError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const open = () => {
    setFocusRaw(raw);
    setFocusError("");
    setFocused(true);
  };
  const close = () => setFocused(false);
  useDialogFocusTrap({
    active: focused,
    containerRef: overlayRef,
    initialFocusRef: textareaRef,
    onEscape: close,
  });
  return (
    <>
      <div className="api-account-json-toolbar">
        <button
          ref={triggerRef}
          type="button"
          className="btn btn-outline"
          disabled={disabled}
          onClick={open}
        >
          专注编辑 JSON
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={disabled}
          onClick={() => onApply()}
        >
          应用 JSON
        </button>
      </div>
      <textarea
        id="api-account-advanced-json"
        className="api-account-json-editor"
        aria-label="完整 advanced_config JSON"
        value={raw}
        aria-invalid={Boolean(error)}
        disabled={disabled}
        onChange={(event) => onRawChange(event.target.value)}
      />
      {error ? (
        <p role="alert" className="api-account-inline-error">
          {error}
        </p>
      ) : null}
      {focused ? (
        <div
          ref={overlayRef}
          className="api-account-focus-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="专注编辑 advanced_config"
        >
          <header>
            <h2>配置 JSON</h2>
            <div>
              <button
                type="button"
                className="btn btn-outline"
                disabled={disabled}
                onClick={() => {
                  try {
                    setFocusRaw(JSON.stringify(JSON.parse(focusRaw), null, 2));
                    setFocusError("");
                  } catch {
                    setFocusError("JSON 格式错误");
                  }
                }}
              >
                格式化
              </button>
              <button
                type="button"
                className="btn btn-outline"
                disabled={disabled}
                onClick={close}
              >
                取消专注编辑
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={disabled}
                onClick={() => {
                  if (onApply(focusRaw)) close();
                  else setFocusError("JSON 格式错误");
                }}
              >
                应用到工作台
              </button>
            </div>
          </header>
          <textarea
            ref={textareaRef}
            aria-label="专注 JSON 编辑器"
            aria-invalid={Boolean(focusError)}
            disabled={disabled}
            value={focusRaw}
            onChange={(event) => setFocusRaw(event.target.value)}
          />
          {focusError ? (
            <p role="alert" className="api-account-inline-error">
              {focusError}
            </p>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
