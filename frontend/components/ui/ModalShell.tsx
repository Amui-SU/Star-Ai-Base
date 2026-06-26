"use client";

import type { ReactNode } from "react";

interface ModalShellProps {
  children: ReactNode;
  cardClassName: string;
  onClose: () => void;
  backdropClassName?: string;
  eventType?: "mouse" | "click";
}

export default function ModalShell({
  children,
  cardClassName,
  onClose,
  backdropClassName = "",
  eventType = "mouse",
}: ModalShellProps) {
  const backdropClass = ["modal-backdrop", backdropClassName]
    .filter(Boolean)
    .join(" ");
  const cardClass = ["modal-card", cardClassName].filter(Boolean).join(" ");

  if (eventType === "click") {
    return (
      <div className={backdropClass} onClick={onClose}>
        <div className={cardClass} onClick={(event) => event.stopPropagation()}>
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className={backdropClass} onMouseDown={onClose}>
      <div
        className={cardClass}
        onMouseDown={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
