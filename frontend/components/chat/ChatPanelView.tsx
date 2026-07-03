"use client";

import type { ComponentProps, RefObject, UIEventHandler } from "react";

import ChatPanelComposerSection from "@/components/chat/ChatPanelComposerSection";
import ChatEmptyState from "@/components/chat/ChatEmptyState";
import ChatPanelHeader from "@/components/chat/ChatPanelHeader";
import MessageList from "@/components/chat/MessageList";
import ModelConfigModal from "@/components/chat/ModelConfigModal";
import WebSearchConfigModal from "@/components/chat/WebSearchConfigModal";
import type { Message } from "@/components/chat/types";

interface ChatPanelViewProps {
  headerProps: ComponentProps<typeof ChatPanelHeader>;
  messages: Message[];
  chatScrollRef: RefObject<HTMLDivElement | null>;
  onChatScroll: UIEventHandler<HTMLDivElement>;
  emptyStateProps: ComponentProps<typeof ChatEmptyState>;
  messageListProps: Omit<ComponentProps<typeof MessageList>, "messages">;
  composerProps: ComponentProps<typeof ChatPanelComposerSection>;
  webSearchModalProps: ComponentProps<typeof WebSearchConfigModal> | null;
  modelConfigModalProps: ComponentProps<typeof ModelConfigModal> | null;
}

export default function ChatPanelView({
  headerProps,
  messages,
  chatScrollRef,
  onChatScroll,
  emptyStateProps,
  messageListProps,
  composerProps,
  webSearchModalProps,
  modelConfigModalProps,
}: ChatPanelViewProps) {
  return (
    <div className="panel-inner">
      <ChatPanelHeader {...headerProps} />

      <div className="panel-body">
        <div
          className="chat-scroll"
          ref={chatScrollRef}
          onScroll={onChatScroll}
        >
          {messages.length === 0 ? (
            <ChatEmptyState {...emptyStateProps} />
          ) : (
            <MessageList messages={messages} {...messageListProps} />
          )}
        </div>
      </div>

      <ChatPanelComposerSection {...composerProps} />

      {webSearchModalProps && <WebSearchConfigModal {...webSearchModalProps} />}
      {modelConfigModalProps && <ModelConfigModal {...modelConfigModalProps} />}
    </div>
  );
}
