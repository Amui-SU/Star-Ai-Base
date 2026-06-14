"use client";

import { useEffect, useState } from "react";

interface Props {
  active: boolean;
  startedAt: number;
  durationMs?: number;
  thinking?: string;
}

export function formatThinkingDuration(durationMs: number): string {
  return `${Math.max(0, durationMs / 1000).toFixed(1)} 秒`;
}

export default function ThinkingProcess({
  active,
  startedAt,
  durationMs,
  thinking = "",
}: Props) {
  const [now, setNow] = useState(() => Date.now());
  const [manuallyExpanded, setManuallyExpanded] = useState(false);

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, [active, startedAt]);

  if (!active && !thinking.trim()) return null;

  const elapsed = active ? now - startedAt : (durationMs ?? now - startedAt);
  const label = active
    ? `正在思考 · ${formatThinkingDuration(elapsed)}`
    : `已思考 ${formatThinkingDuration(elapsed)}`;
  const expanded = active || manuallyExpanded;

  return (
    <div className={`thinking-process ${active ? "active" : "complete"}`}>
      <button
        type="button"
        className="thinking-process-trigger"
        onClick={() => {
          if (!active) setManuallyExpanded((value) => !value);
        }}
        aria-expanded={expanded}
      >
        <span
          className={`thinking-process-chevron ${expanded ? "expanded" : ""}`}
          aria-hidden="true"
        >
          ›
        </span>
        <span>{label}</span>
        {!active && (
          <span className="thinking-process-hint">
            {expanded ? "点击收起" : "点击展开"}
          </span>
        )}
      </button>
      {expanded && thinking.trim() && (
        <div className="thinking-process-content">{thinking}</div>
      )}
    </div>
  );
}
