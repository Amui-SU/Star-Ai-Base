import { useEffect, useRef, useState } from "react";

export default function AdvancedConfigEditor({
  raw,
  error,
  onRawChange,
  onApply,
}: {
  raw: string;
  error: string;
  onRawChange: (raw: string) => void;
  onApply: (raw?: string) => boolean;
}) {
  const [focused, setFocused] = useState(false);
  const [focusRaw, setFocusRaw] = useState("");
  const [focusError, setFocusError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const open = () => {
    setFocusRaw(raw);
    setFocusError("");
    setFocused(true);
  };
  const close = () => setFocused(false);
  useEffect(() => {
    if (focused) textareaRef.current?.focus();
  }, [focused]);
  useEffect(() => {
    if (!focused) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        overlayRef.current?.querySelectorAll<HTMLElement>("button, textarea") ??
          [],
      );
      if (!focusable.length) return;
      const current = focusable.indexOf(document.activeElement as HTMLElement);
      const next = event.shiftKey
        ? current <= 0
          ? focusable.length - 1
          : current - 1
        : current === focusable.length - 1
          ? 0
          : current + 1;
      event.preventDefault();
      focusable[next]?.focus();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [focused]);
  return (
    <>
      <div className="api-account-json-toolbar">
        <button type="button" className="btn btn-outline" onClick={open}>
          专注编辑 JSON
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => onApply()}
        >
          应用 JSON
        </button>
      </div>
      <textarea
        className="api-account-json-editor"
        aria-label="完整 advanced_config JSON"
        value={raw}
        aria-invalid={Boolean(error)}
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
              <button type="button" className="btn btn-outline" onClick={close}>
                取消专注编辑
              </button>
              <button
                type="button"
                className="btn btn-primary"
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
