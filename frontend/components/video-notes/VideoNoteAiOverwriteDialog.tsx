"use client";

import { useRef } from "react";

import ModalShell from "@/components/ui/ModalShell";
import { useDialogFocusTrap } from "@/components/ui/useDialogFocusTrap";

interface VideoNoteAiOverwriteDialogProps {
  targets: string[];
  onCancel: () => void;
  onConfirm: () => void;
}

export default function VideoNoteAiOverwriteDialog({
  targets,
  onCancel,
  onConfirm,
}: VideoNoteAiOverwriteDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useDialogFocusTrap({
    containerRef: dialogRef,
    initialFocusRef: cancelRef,
    onEscape: onCancel,
  });

  return (
    <ModalShell
      cardClassName="video-note-ai-overwrite-card"
      backdropClassName="video-note-ai-overwrite-backdrop"
      onClose={onCancel}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="video-note-ai-overwrite-title"
        tabIndex={-1}
      >
        <h2 id="video-note-ai-overwrite-title">覆盖现有内容？</h2>
        <p>继续生成将覆盖以下已有内容：</p>
        <ul>
          {targets.map((target) => (
            <li key={target}>{target}</li>
          ))}
        </ul>
        <div className="video-note-ai-overwrite-actions">
          <button ref={cancelRef} type="button" onClick={onCancel}>
            取消
          </button>
          <button type="button" onClick={onConfirm}>
            继续生成并覆盖
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
