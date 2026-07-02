"use client";

import type { ComponentProps } from "react";

import ChatModelStatus from "@/components/chat/ChatModelStatus";

interface ChatPanelHeaderProps extends ComponentProps<typeof ChatModelStatus> {
  knowledgeBaseTitle: string;
  totalVideos?: number | null;
}

export default function ChatPanelHeader({
  knowledgeBaseTitle,
  totalVideos,
  ...modelStatusProps
}: ChatPanelHeaderProps) {
  return (
    <div className="chat-context-row">
      <div className="chat-context-actions">
        <div className="chat-kb-context">
          {knowledgeBaseTitle}
          {(totalVideos ?? 0) > 0 && (
            <span className="chat-kb-meta"> · {totalVideos} 个视频</span>
          )}
        </div>
        <ChatModelStatus {...modelStatusProps} />
      </div>
    </div>
  );
}
