import type { ChatResponse } from "@/lib/api";
import type { ParsedChatStream } from "@/lib/chatStream";
import type { Message } from "@/components/chat/types";

interface ThinkingExtraction {
  answer: string;
  thinking?: string;
}

export function extractThinkingFromContent(
  content: string,
): ThinkingExtraction {
  const text = content || "";
  const thinkTagMatch = text.match(/<think>([\s\S]*?)<\/think>/i);
  if (thinkTagMatch) {
    return {
      thinking: thinkTagMatch[1].trim(),
      answer: text.replace(thinkTagMatch[0], "").trim(),
    };
  }

  const markdownMatch = text.match(
    /(?:^|\n)\s*(?:思考过程|思考|推理过程)[:：]\s*([\s\S]*?)(?:\n\s*(?:最终回答|回答|答案)[:：]\s*([\s\S]*))?$/i,
  );
  if (markdownMatch && markdownMatch[1]) {
    return {
      thinking: markdownMatch[1].trim(),
      answer: (markdownMatch[2] || text.slice(0, markdownMatch.index)).trim(),
    };
  }

  return { answer: text.trim() };
}

export function updateAssistantMessage(
  messages: Message[],
  assistantId: string,
  update: (message: Message) => Message,
): Message[] {
  return messages.map((message) =>
    message.id === assistantId ? update(message) : message,
  );
}

export function startAssistantStreaming(
  message: Message,
  thinkingStartedAt: number,
): Message {
  return {
    ...message,
    thinking: "",
    thinkingActive: true,
    thinkingStartedAt,
    thinkingDurationMs: undefined,
    webSearchActive: false,
    webSearchProgress: undefined,
  };
}

export function applyParsedStreamUpdate(
  message: Message,
  parsed: ParsedChatStream,
): Message {
  return {
    ...message,
    content: parsed.answer,
    thinking: parsed.thinking || message.thinking,
    webSearchActive:
      parsed.webSearchProgress !== undefined
        ? Boolean(parsed.webSearchProgress)
        : message.webSearchActive,
    webSearchProgress:
      parsed.webSearchProgress !== undefined
        ? parsed.webSearchProgress || undefined
        : message.webSearchProgress,
    sources: parsed.complete ? parsed.sources : message.sources,
    webSearch: parsed.webSearch || message.webSearch,
  };
}

export function finalizeStreamedAssistantAnswer(
  message: Message,
  parsed: ParsedChatStream,
): Message {
  const extracted = extractThinkingFromContent(parsed.answer);
  const finalThinking = (parsed.thinking || extracted.thinking || "").trim();

  return {
    ...message,
    content: extracted.answer,
    thinking: finalThinking || undefined,
    webSearchActive: false,
    webSearchProgress: undefined,
    sources: parsed.sources,
    webSearch: parsed.webSearch,
  };
}

export function finalizeFallbackAssistantAnswer(
  message: Message,
  response: ChatResponse,
): Message {
  const extracted = extractThinkingFromContent(response.answer || "");
  const finalThinking = (response.thinking || extracted.thinking || "").trim();
  const finalAnswer = response.thinking
    ? (response.answer || "").trim() ||
      (finalThinking ? "（已生成思考过程，展开查看）" : "")
    : extracted.answer;

  return {
    ...message,
    content: finalAnswer,
    thinking: finalThinking || undefined,
    webSearchActive: false,
    webSearchProgress: undefined,
    sources: response.sources,
    webSearch: response.web_search,
  };
}

export function applyAssistantError(
  message: Message,
  errorMessage: string,
): Message {
  return {
    ...message,
    content: `错误: ${errorMessage}`,
    webSearchActive: false,
    webSearchProgress: undefined,
  };
}

export function resetAssistantForRegeneration(message: Message): Message {
  return {
    ...message,
    content: "",
    thinking: undefined,
    thinkingActive: false,
    thinkingStartedAt: undefined,
    thinkingDurationMs: undefined,
    webSearchActive: false,
    webSearchProgress: undefined,
    sources: [],
    webSearch: undefined,
  };
}
