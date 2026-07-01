"use client";

interface ChatScopeTriggerProps {
  open: boolean;
  disabled: boolean;
  webSearchEnabled: boolean;
  webSearchNotice: string;
  triggerSummary: string;
  accessibleSummary: string;
  onToggleOpen: () => void;
}

export default function ChatScopeTrigger({
  open,
  disabled,
  webSearchEnabled,
  webSearchNotice,
  triggerSummary,
  accessibleSummary,
  onToggleOpen,
}: ChatScopeTriggerProps) {
  return (
    <button
      type="button"
      className={`mode-chip scope-picker-trigger ${
        webSearchEnabled ? "web-search-enabled" : ""
      } ${webSearchNotice ? "web-search-notice" : ""}`}
      disabled={disabled}
      onClick={onToggleOpen}
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-label={`提问范围：${accessibleSummary}`}
      title={`提问范围：${accessibleSummary}`}
    >
      <span aria-hidden="true">◎</span>
      <span className="scope-picker-summary">{triggerSummary}</span>
    </button>
  );
}
