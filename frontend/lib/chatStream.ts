export interface ChatStreamSource {
  bvid?: string;
  title: string;
  url: string;
  type?: "knowledge" | "web" | string;
}

export interface ChatWebSearchStatus {
  status: "success" | "no_results" | "failed" | string;
  message: string;
  result_count?: number;
  queries?: string[];
  results?: Array<{
    title: string;
    url: string;
    snippet?: string;
  }>;
  errors?: Array<{
    source?: string;
    query?: string;
    url?: string;
    message: string;
  }>;
}

export interface ParsedChatStream {
  answer: string;
  thinking: string;
  webSearchProgress?: string;
  sources: ChatStreamSource[];
  webSearch?: ChatWebSearchStatus;
  complete: boolean;
}

const THINKING_DELTA_MARKER = "[[THINKING_DELTA]]";
const WEB_SEARCH_PROGRESS_MARKER = "[[WEB_SEARCH_PROGRESS]]";
const THINKING_MARKER = "[[THINKING_JSON]]";
const WEB_SEARCH_MARKER = "[[WEB_SEARCH_JSON]]";
const SOURCES_MARKER = "[[SOURCES_JSON]]";
const COMPLETE_THINKING_DELTA =
  /\[\[THINKING_DELTA\]\]("(?:\\.|[^"\\])*")\r?\n/g;
const COMPLETE_WEB_SEARCH_PROGRESS =
  /\[\[WEB_SEARCH_PROGRESS\]\]("(?:\\.|[^"\\])*")\r?\n/g;

function parseJson<T>(value: string, fallback: T): T {
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function parseJsonValue(value: string): unknown {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return undefined;
  }
}

function findLastMetadataMarker(
  value: string,
  marker: string,
  before = value.length,
): number {
  const escapedMarker = marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`(?:^|\\r?\\n)${escapedMarker}`, "g");
  let result = -1;
  for (const match of value.matchAll(pattern)) {
    const index = match.index + match[0].length - marker.length;
    if (index < before) result = index;
  }
  return result;
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
  let webSearchProgress: string | undefined;
  visible = visible.replace(
    COMPLETE_WEB_SEARCH_PROGRESS,
    (_, encoded: string) => {
      webSearchProgress = parseJson(encoded, "");
      return "";
    },
  );

  const partialDeltaIndex = visible.lastIndexOf(THINKING_DELTA_MARKER);
  if (partialDeltaIndex >= 0) {
    visible = visible.slice(0, partialDeltaIndex);
  }
  const partialProgressIndex = visible.lastIndexOf(WEB_SEARCH_PROGRESS_MARKER);
  if (partialProgressIndex >= 0) {
    visible = visible.slice(0, partialProgressIndex);
  }

  let sourcesIndex = findLastMetadataMarker(visible, SOURCES_MARKER);
  let finalThinking = "";
  let webSearch: ChatWebSearchStatus | undefined;
  let sources: ChatStreamSource[] = [];
  let metadataStart = sourcesIndex >= 0 ? sourcesIndex : visible.length;

  if (sourcesIndex >= 0) {
    const parsed = parseJsonValue(
      visible.slice(sourcesIndex + SOURCES_MARKER.length).trim(),
    );
    if (Array.isArray(parsed)) {
      sources = parsed as ChatStreamSource[];
    } else {
      sourcesIndex = -1;
      metadataStart = visible.length;
    }
  }

  const webSearchIndex = findLastMetadataMarker(
    visible,
    WEB_SEARCH_MARKER,
    metadataStart,
  );
  if (webSearchIndex >= 0 && sourcesIndex >= 0) {
    const start = webSearchIndex + WEB_SEARCH_MARKER.length;
    const parsed = parseJsonValue(visible.slice(start, metadataStart).trim());
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      webSearch = parsed as ChatWebSearchStatus;
      metadataStart = webSearchIndex;
    }
  }

  const thinkingIndex = findLastMetadataMarker(
    visible,
    THINKING_MARKER,
    metadataStart,
  );
  if (thinkingIndex >= 0) {
    const start = thinkingIndex + THINKING_MARKER.length;
    const parsed = parseJsonValue(visible.slice(start, metadataStart).trim());
    if (typeof parsed === "string") {
      finalThinking = parsed;
      metadataStart = thinkingIndex;
    }
  }
  const answer = visible.slice(0, metadataStart).trim();

  return {
    answer,
    thinking: finalThinking || thinkingFromDeltas,
    webSearchProgress,
    sources,
    webSearch,
    complete: sourcesIndex >= 0,
  };
}
