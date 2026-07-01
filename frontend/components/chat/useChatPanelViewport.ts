"use client";

import { useCallback, useEffect, useRef, type UIEvent } from "react";
import type { Message } from "@/components/chat/types";

const CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD_PX = 96;
const COMPOSER_MIN_HEIGHT_PX = 54;
const COMPOSER_MAX_HEIGHT_PX = 180;

function isNearScrollBottom(element: HTMLElement) {
  return (
    element.scrollHeight - element.scrollTop - element.clientHeight <=
    CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD_PX
  );
}

interface UseChatPanelViewportParams {
  input: string;
  messages: Message[];
  onInputChange: (value: string) => void;
  shouldFollowChatScrollRef: React.MutableRefObject<boolean>;
}

export function useChatPanelViewport({
  input,
  messages,
  onInputChange,
  shouldFollowChatScrollRef,
}: UseChatPanelViewportParams) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const scrollFrameRef = useRef<number | null>(null);

  const handleChatScroll = useCallback(
    (event: UIEvent<HTMLDivElement>) => {
      const shouldFollow = isNearScrollBottom(event.currentTarget);
      shouldFollowChatScrollRef.current = shouldFollow;
      if (!shouldFollow && scrollFrameRef.current !== null) {
        window.cancelAnimationFrame(scrollFrameRef.current);
        scrollFrameRef.current = null;
      }
    },
    [shouldFollowChatScrollRef],
  );

  useEffect(() => {
    if (scrollFrameRef.current !== null) {
      window.cancelAnimationFrame(scrollFrameRef.current);
      scrollFrameRef.current = null;
    }
    if (!shouldFollowChatScrollRef.current) {
      return;
    }
    scrollFrameRef.current = window.requestAnimationFrame(() => {
      scrollFrameRef.current = null;
      endRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
    });
    return () => {
      if (scrollFrameRef.current !== null) {
        window.cancelAnimationFrame(scrollFrameRef.current);
        scrollFrameRef.current = null;
      }
    };
  }, [messages, shouldFollowChatScrollRef]);

  const adjustComposerHeight = useCallback(
    (el?: HTMLTextAreaElement | null) => {
      const textarea = el || inputRef.current;
      if (!textarea) return;
      textarea.style.height = "auto";
      const nextHeight = Math.min(
        Math.max(textarea.scrollHeight, COMPOSER_MIN_HEIGHT_PX),
        COMPOSER_MAX_HEIGHT_PX,
      );
      textarea.style.height = `${nextHeight}px`;
      textarea.style.overflowY =
        textarea.scrollHeight > COMPOSER_MAX_HEIGHT_PX ? "auto" : "hidden";
    },
    [],
  );

  const handleComposerChange = useCallback(
    (value: string, target?: HTMLTextAreaElement | null) => {
      onInputChange(value);
      adjustComposerHeight(target);
    },
    [adjustComposerHeight, onInputChange],
  );

  useEffect(() => {
    adjustComposerHeight();
  }, [adjustComposerHeight, input]);

  return {
    chatScrollRef,
    endRef,
    handleChatScroll,
    handleComposerChange,
    inputRef,
  };
}
