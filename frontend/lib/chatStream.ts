export interface ChatStreamSource {
  bvid: string;
  title: string;
  url: string;
}

export interface ParsedChatStream {
  answer: string;
  thinking: string;
  sources: ChatStreamSource[];
  complete: boolean;
}

const THINKING_DELTA_MARKER = "[[THINKING_DELTA]]";
const THINKING_MARKER = "[[THINKING_JSON]]";
const SOURCES_MARKER = "[[SOURCES_JSON]]";
const COMPLETE_THINKING_DELTA =
  /\[\[THINKING_DELTA\]\]("(?:\\.|[^"\\])*")\r?\n/g;

function parseJson<T>(value: string, fallback: T): T {
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

export function parseChatStream(buffer: string): ParsedChatStream {
  let thinkingFromDeltas = "";
  let visible = buffer.replace(
    COMPLETE_THINKING_DELTA,
    (_, encoded: string) => {
      thinkingFromDeltas += parseJson(encoded, "");
      return "";
    },
  );

  const partialDeltaIndex = visible.lastIndexOf(THINKING_DELTA_MARKER);
  if (partialDeltaIndex >= 0) {
    visible = visible.slice(0, partialDeltaIndex);
  }

  const thinkingIndex = visible.indexOf(THINKING_MARKER);
  const sourcesIndex = visible.indexOf(SOURCES_MARKER);
  const metadataIndexes = [thinkingIndex, sourcesIndex].filter(
    (index) => index >= 0,
  );
  const answerEnd =
    metadataIndexes.length > 0 ? Math.min(...metadataIndexes) : visible.length;
  const answer = visible.slice(0, answerEnd).trim();

  let finalThinking = "";
  if (thinkingIndex >= 0) {
    const start = thinkingIndex + THINKING_MARKER.length;
    const end = sourcesIndex >= start ? sourcesIndex : visible.length;
    finalThinking = parseJson(visible.slice(start, end).trim(), "");
  }

  let sources: ChatStreamSource[] = [];
  if (sourcesIndex >= 0) {
    const parsed = parseJson<unknown>(
      visible.slice(sourcesIndex + SOURCES_MARKER.length).trim(),
      [],
    );
    if (Array.isArray(parsed)) {
      sources = parsed as ChatStreamSource[];
    }
  }

  return {
    answer,
    thinking: finalThinking || thinkingFromDeltas,
    sources,
    complete: sourcesIndex >= 0,
  };
}
