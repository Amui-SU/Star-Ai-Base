"use client";

import type { ReactNode } from "react";

interface VideoNoteDrawerProps {
  children: ReactNode;
  fullscreen: boolean;
}

export default function VideoNoteDrawer({
  children,
  fullscreen,
}: VideoNoteDrawerProps) {
  return (
    <div className={`video-note-drawer ${fullscreen ? "fullscreen" : ""}`}>
      {children}
    </div>
  );
}
