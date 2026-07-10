"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";

import type { VideoNoteBlock, VideoNoteVideo } from "@/lib/api";
import {
  blocksToMarkdown,
  markdownToVideoNoteBlocks,
} from "./videoNoteMarkdownAdapter";

interface VideoNoteMarkdownEditorProps {
  blocks: VideoNoteBlock[];
  onChange: (blocks: VideoNoteBlock[]) => void;
  onSeekTo?: (timeInSeconds: number) => void;
  bvid?: string;
  video?: VideoNoteVideo | null;
}

type VditorInstance = import("vditor").default;
type UndoRedoKeyboardEvent = Pick<
  KeyboardEvent,
  | "altKey"
  | "ctrlKey"
  | "defaultPrevented"
  | "key"
  | "metaKey"
  | "preventDefault"
  | "shiftKey"
>;

export function buildBilibiliTimestampUrl(
  bvid: string,
  timeInSeconds: number,
  video?: VideoNoteVideo | null,
) {
  const safeSeconds = Number.isFinite(timeInSeconds)
    ? Math.max(0, Math.floor(timeInSeconds))
    : 0;
  const currentPart = video?.parts?.[0];
  const page =
    typeof currentPart?.page === "number" && Number.isFinite(currentPart.page)
      ? Math.max(1, Math.floor(currentPart.page))
      : null;

  if (page !== null) {
    return `https://www.bilibili.com/video/${bvid}?p=${page}&t=${safeSeconds}`;
  }
  return `https://www.bilibili.com/video/${bvid}?t=${safeSeconds}`;
}

interface CaretPositionAtPoint {
  offset: number;
  offsetNode: Node;
}

type DocumentWithCaretPoint = Document & {
  caretPositionFromPoint?: (
    x: number,
    y: number,
  ) => CaretPositionAtPoint | null;
  caretRangeFromPoint?: (x: number, y: number) => Range | null;
};

interface PlainUrlMatch {
  end: number;
  start: number;
  url: string;
}

const PLAIN_URL_CLASS = "video-plain-url-link";
const PLAIN_URL_SELECTOR = `.${PLAIN_URL_CLASS}`;
const PLAIN_URL_PATTERN = /https?:\/\/[^\s<>"'`]+/g;

function isHttpUrl(value: string | null): value is string {
  return value !== null && /^https?:\/\//.test(value);
}

function trimPlainUrl(rawUrl: string) {
  return rawUrl.replace(/[),.，。！？!?;；:：]+$/u, "");
}

function findPlainUrlMatches(text: string): PlainUrlMatch[] {
  const matches: PlainUrlMatch[] = [];

  for (const match of text.matchAll(PLAIN_URL_PATTERN)) {
    const url = trimPlainUrl(match[0]);
    if (url.length === 0) continue;

    const start = match.index ?? 0;
    matches.push({
      end: start + url.length,
      start,
      url,
    });
  }

  return matches;
}

function findHttpAnchor(
  target: EventTarget | null,
  boundary: Element,
): HTMLAnchorElement | null {
  const start =
    target instanceof Element
      ? target
      : target instanceof Node
        ? target.parentElement
        : null;
  let element: Element | null = start;

  while (element && element !== boundary) {
    if (element.tagName === "A") {
      const anchor = element as HTMLAnchorElement;
      return isHttpUrl(anchor.getAttribute("href")) ? anchor : null;
    }
    element = element.parentElement;
  }

  return null;
}

function findPlainUrlAtOffset(
  text: string,
  offset: number,
): PlainUrlMatch | null {
  if (!Number.isFinite(offset) || offset < 0) return null;

  for (const match of findPlainUrlMatches(text)) {
    if (offset >= match.start && offset <= match.end) {
      return match;
    }
  }

  return null;
}

function findMarkedPlainUrl(
  target: EventTarget | null,
  boundary: Element,
): string | null {
  const start =
    target instanceof Element
      ? target
      : target instanceof Node
        ? target.parentElement
        : null;
  let element: Element | null = start;

  while (element && element !== boundary) {
    if (
      element instanceof HTMLElement &&
      element.classList.contains(PLAIN_URL_CLASS)
    ) {
      const url = element.dataset.url ?? element.textContent;
      return isHttpUrl(url) ? url : null;
    }
    element = element.parentElement;
  }

  return null;
}

function shouldSkipPlainUrlTextNode(textNode: Text) {
  const parent = textNode.parentElement;
  return (
    parent === null ||
    Boolean(parent.closest(`a, .video-timestamp-link, ${PLAIN_URL_SELECTOR}`))
  );
}

function wrapPlainUrlsInTextNode(textNode: Text) {
  if (shouldSkipPlainUrlTextNode(textNode)) return;

  const text = textNode.textContent ?? "";
  const matches = findPlainUrlMatches(text);
  if (matches.length === 0) return;

  const fragment = textNode.ownerDocument.createDocumentFragment();
  let cursor = 0;

  matches.forEach((match) => {
    if (match.start < cursor) return;
    if (match.start > cursor) {
      fragment.append(text.slice(cursor, match.start));
    }

    const urlSpan = textNode.ownerDocument.createElement("span");
    urlSpan.className = PLAIN_URL_CLASS;
    urlSpan.dataset.url = match.url;
    urlSpan.textContent = match.url;
    urlSpan.style.cursor = "pointer";
    fragment.append(urlSpan);
    cursor = match.end;
  });

  if (cursor < text.length) {
    fragment.append(text.slice(cursor));
  }

  textNode.replaceWith(fragment);
}

function markPlainUrlsInElement(element: HTMLElement) {
  const nodeFilter = element.ownerDocument.defaultView?.NodeFilter;
  if (!nodeFilter) return;

  const textNodes: Text[] = [];
  const walker = element.ownerDocument.createTreeWalker(
    element,
    nodeFilter.SHOW_TEXT,
    {
      acceptNode(node) {
        if (
          node.nodeType !== Node.TEXT_NODE ||
          !node.textContent?.match(PLAIN_URL_PATTERN)
        ) {
          return nodeFilter.FILTER_REJECT;
        }
        return shouldSkipPlainUrlTextNode(node as Text)
          ? nodeFilter.FILTER_REJECT
          : nodeFilter.FILTER_ACCEPT;
      },
    },
  );

  while (walker.nextNode()) {
    textNodes.push(walker.currentNode as Text);
  }

  textNodes.forEach(wrapPlainUrlsInTextNode);
}

function getCaretRangeFromPoint(event: MouseEvent): Range | null {
  const ownerDocument = event.view?.document ?? document;
  const documentWithCaret = ownerDocument as DocumentWithCaretPoint;
  const caretPosition = documentWithCaret.caretPositionFromPoint?.(
    event.clientX,
    event.clientY,
  );

  if (caretPosition) {
    const range = ownerDocument.createRange();
    range.setStart(caretPosition.offsetNode, caretPosition.offset);
    range.collapse(true);
    return range;
  }

  return (
    documentWithCaret.caretRangeFromPoint?.(event.clientX, event.clientY) ??
    null
  );
}

function pointHitsTextRange(
  event: MouseEvent,
  textNode: Text,
  match: PlainUrlMatch,
  offset: number,
) {
  const range = textNode.ownerDocument.createRange();
  range.setStart(textNode, match.start);
  range.setEnd(textNode, match.end);
  const rects = range.getClientRects ? Array.from(range.getClientRects()) : [];

  if (rects.length === 0) {
    return offset < match.end;
  }

  return rects.some(
    (rect) =>
      event.clientX >= rect.left &&
      event.clientX <= rect.right &&
      event.clientY >= rect.top &&
      event.clientY <= rect.bottom,
  );
}

function findPlainHttpUrlAtClick(
  event: MouseEvent,
  boundary: Element,
): string | null {
  const range = getCaretRangeFromPoint(event);
  if (!range || range.startContainer.nodeType !== Node.TEXT_NODE) {
    return null;
  }
  const textNode = range.startContainer as Text;
  if (!boundary.contains(textNode)) return null;

  const match = findPlainUrlAtOffset(
    textNode.textContent ?? "",
    range.startOffset,
  );
  if (!match) return null;

  return pointHitsTextRange(event, textNode, match, range.startOffset)
    ? match.url
    : null;
}

export default function VideoNoteMarkdownEditor({
  blocks,
  onChange,
  onSeekTo,
  bvid,
  video,
}: VideoNoteMarkdownEditorProps) {
  const editorId = `video-note-vditor-${useId().replace(/:/g, "")}`;
  const markdown = useMemo(() => blocksToMarkdown(blocks), [blocks]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const vditorHostRef = useRef<HTMLDivElement | null>(null);
  const editorRef = useRef<VditorInstance | null>(null);
  const blocksRef = useRef(blocks);
  const onChangeRef = useRef(onChange);
  const lastMarkdownRef = useRef(markdown);
  const undoStackRef = useRef<string[]>([]);
  const redoStackRef = useRef<string[]>([]);
  const applyingHistoryRef = useRef(false);
  const pendingLocalChangeRef = useRef<{
    blocks: VideoNoteBlock[];
    echoMarkdown: string;
    rawMarkdown: string;
  } | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    blocksRef.current = blocks;
  }, [blocks]);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const emitMarkdownChange = useCallback((value: string) => {
    const nextBlocks = markdownToVideoNoteBlocks(value, blocksRef.current);
    pendingLocalChangeRef.current = {
      blocks: nextBlocks,
      echoMarkdown: blocksToMarkdown(nextBlocks),
      rawMarkdown: value,
    };
    onChangeRef.current(nextBlocks);
  }, []);

  const applyMarkdownValue = useCallback(
    (value: string) => {
      const editor = editorRef.current;
      if (editor?.getValue() !== value) {
        editor?.setValue(value);
      }
      lastMarkdownRef.current = value;
      emitMarkdownChange(value);
    },
    [emitMarkdownChange],
  );

  const recordMarkdownInput = useCallback(
    (value: string) => {
      if (!applyingHistoryRef.current && lastMarkdownRef.current !== value) {
        undoStackRef.current.push(lastMarkdownRef.current);
        if (undoStackRef.current.length > 100) {
          undoStackRef.current.shift();
        }
        redoStackRef.current = [];
      }
      lastMarkdownRef.current = value;
      emitMarkdownChange(value);
    },
    [emitMarkdownChange],
  );

  const recordPendingEditorValue = useCallback(() => {
    const editor = editorRef.current;
    if (!editor || applyingHistoryRef.current) return;
    const value = editor.getValue();
    if (lastMarkdownRef.current === value) return;
    recordMarkdownInput(value);
  }, [recordMarkdownInput]);

  const undoMarkdown = useCallback(() => {
    const previous = undoStackRef.current.pop();
    if (previous === undefined) return;
    const editor = editorRef.current;
    const current = editor?.getValue() ?? lastMarkdownRef.current;
    redoStackRef.current.push(current);
    applyingHistoryRef.current = true;
    applyMarkdownValue(previous);
    applyingHistoryRef.current = false;
  }, [applyMarkdownValue]);

  const redoMarkdown = useCallback(() => {
    const next = redoStackRef.current.pop();
    if (next === undefined) return;
    const editor = editorRef.current;
    const current = editor?.getValue() ?? lastMarkdownRef.current;
    undoStackRef.current.push(current);
    applyingHistoryRef.current = true;
    applyMarkdownValue(next);
    applyingHistoryRef.current = false;
  }, [applyMarkdownValue]);

  const handleUndoRedoShortcut = useCallback(
    (event: UndoRedoKeyboardEvent) => {
      if (event.defaultPrevented) return;
      const isModifierPressed = event.ctrlKey || event.metaKey;
      if (!isModifierPressed || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "z" && !event.shiftKey) {
        recordPendingEditorValue();
        if (undoStackRef.current.length === 0) return;
        event.preventDefault();
        undoMarkdown();
        return;
      }
      if (key === "y" || (key === "z" && event.shiftKey)) {
        if (redoStackRef.current.length === 0) return;
        event.preventDefault();
        redoMarkdown();
      }
    },
    [recordPendingEditorValue, redoMarkdown, undoMarkdown],
  );

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    handleUndoRedoShortcut(event);
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handleNativeKeyDown = (event: KeyboardEvent) => {
      handleUndoRedoShortcut(event);
    };
    container.addEventListener("keydown", handleNativeKeyDown, true);
    return () => {
      container.removeEventListener("keydown", handleNativeKeyDown, true);
    };
  }, [handleUndoRedoShortcut]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handleNativeInput = () => {
      const editor = editorRef.current;
      if (!editor || applyingHistoryRef.current) return;
      recordMarkdownInput(editor.getValue());
    };
    container.addEventListener("input", handleNativeInput, true);
    return () => {
      container.removeEventListener("input", handleNativeInput, true);
    };
  }, [recordMarkdownInput]);

  useEffect(() => {
    let cancelled = false;
    let mountedEditor: VditorInstance | null = null;
    const cleanupEditorEnhancements: Array<() => void> = [];

    async function mountEditor() {
      try {
        const [{ default: Vditor }] = await Promise.all([
          import("vditor"),
          import("vditor/dist/js/i18n/zh_CN.js"),
        ]);
        if (cancelled) return;
        const host = vditorHostRef.current;
        if (!host) return;

        mountedEditor = new Vditor(host, {
          cache: { enable: false },
          height: "auto",
          i18n: window.VditorI18n,
          lang: "zh_CN",
          minHeight: 420,
          mode: "ir",
          placeholder: "开始记录这段视频里的观点、问题和行动项...",
          theme: document.documentElement.classList.contains("light")
            ? "classic"
            : "dark",
          toolbar: [
            "headings",
            "bold",
            "italic",
            "strike",
            "|",
            "list",
            "ordered-list",
            "check",
            "quote",
            "code",
            "table",
            "|",
            "link",
            "|",
            "undo",
            "redo",
            "|",
            "preview",
            "fullscreen",
          ],
          value: lastMarkdownRef.current,
          input(value) {
            recordMarkdownInput(value);
          },
          after() {
            // 监听编辑器内的点击事件，处理时间戳和链接
            const editorContent = host.querySelector(".vditor-ir");
            if (editorContent) {
              const handleEditorClick = (event: Event) => {
                if (!(event instanceof MouseEvent)) return;
                const target =
                  event.target instanceof HTMLElement
                    ? event.target
                    : event.target instanceof Node
                      ? event.target.parentElement
                      : null;
                if (!target) return;

                // 处理链接点击 - 向上查找<a>标签
                const anchor = findHttpAnchor(target, editorContent);
                if (anchor) {
                  event.preventDefault();
                  event.stopPropagation();
                  window.open(anchor.href, "_blank", "noopener,noreferrer");
                  return;
                }

                const markedPlainUrl = findMarkedPlainUrl(
                  target,
                  editorContent,
                );
                if (markedPlainUrl) {
                  event.preventDefault();
                  event.stopPropagation();
                  window.open(markedPlainUrl, "_blank", "noopener,noreferrer");
                  return;
                }

                const plainUrl = findPlainHttpUrlAtClick(event, editorContent);
                if (plainUrl) {
                  event.preventDefault();
                  event.stopPropagation();
                  window.open(plainUrl, "_blank", "noopener,noreferrer");
                  return;
                }

                // 处理时间戳点击 - 只处理标记为时间戳的元素
                let tsElement: HTMLElement | null = target;
                // 只查找最多3层父元素，避免找到包含多个时间戳的祖先元素
                let depth = 0;
                while (tsElement && tsElement !== editorContent && depth < 3) {
                  if (tsElement.classList.contains("video-timestamp-link")) {
                    const text = tsElement.textContent || "";
                    // 匹配时间戳，支持1-3位数字的分钟/小时
                    const timestampMatch = text.match(
                      /^\[(\d{1,3}):(\d{2})(?::(\d{2}))?\]/,
                    );

                    if (timestampMatch) {
                      event.preventDefault();
                      event.stopPropagation();

                      // 判断是 HH:MM:SS 还是 MM:SS 格式
                      const hours = timestampMatch[3]
                        ? parseInt(timestampMatch[1])
                        : 0;
                      const minutes = timestampMatch[3]
                        ? parseInt(timestampMatch[2])
                        : parseInt(timestampMatch[1]);
                      const seconds = timestampMatch[3]
                        ? parseInt(timestampMatch[3])
                        : parseInt(timestampMatch[2]);
                      const totalSeconds =
                        hours * 3600 + minutes * 60 + seconds;

                      if (bvid) {
                        const videoUrl = buildBilibiliTimestampUrl(
                          bvid,
                          totalSeconds,
                          video,
                        );
                        window.open(videoUrl, "_blank", "noopener,noreferrer");
                      } else if (onSeekTo) {
                        onSeekTo(totalSeconds);
                      }
                      return;
                    }
                  }
                  tsElement = tsElement.parentElement;
                  depth++;
                }
              };
              editorContent.addEventListener("click", handleEditorClick);
              cleanupEditorEnhancements.push(() => {
                editorContent.removeEventListener("click", handleEditorClick);
              });

              // 为时间戳添加样式 - 只标记时间戳本身，不包括后面的文字
              const styleTimestamps = () => {
                if (!editorContent) return;

                // 查找所有可能包含时间戳的元素
                const allElements =
                  editorContent.querySelectorAll("li, p, td, th");

                allElements.forEach((elem) => {
                  const htmlElem = elem as HTMLElement;

                  // 检查是否已经有时间戳span
                  if (!htmlElem.querySelector(".video-timestamp-link")) {
                    // 检查第一个文本节点是否以时间戳开头
                    const firstChild = htmlElem.firstChild;
                    if (firstChild && firstChild.nodeType === Node.TEXT_NODE) {
                      const text = firstChild.textContent || "";
                      const timestampMatch = text.match(
                        /^(\[\d{1,3}:\d{2}(?::\d{2})?\])/,
                      );

                      if (timestampMatch) {
                        const timestamp = timestampMatch[1];
                        const restText = text.substring(timestamp.length);

                        // 创建可点击的时间戳span
                        const timestampSpan = document.createElement("span");
                        timestampSpan.textContent = timestamp;
                        timestampSpan.className = "video-timestamp-link";
                        timestampSpan.style.cursor = "pointer";

                        // 替换文本节点
                        const restTextNode = document.createTextNode(restText);
                        htmlElem.replaceChild(restTextNode, firstChild);
                        htmlElem.insertBefore(timestampSpan, restTextNode);
                      }
                    }
                  }

                  markPlainUrlsInElement(htmlElem);
                });
              };

              const timestampTimeouts: Array<ReturnType<typeof setTimeout>> =
                [];
              const scheduleStyleTimestamps = (delay: number) => {
                const timeoutId = setTimeout(styleTimestamps, delay);
                timestampTimeouts.push(timeoutId);
              };

              // 多次尝试标记时间戳，确保所有时间戳都被标记
              [100, 300, 600, 1000, 2000].forEach(scheduleStyleTimestamps);

              const observer = new MutationObserver(() => {
                scheduleStyleTimestamps(50);
              });
              observer.observe(editorContent, {
                childList: true,
                subtree: true,
              });
              cleanupEditorEnhancements.push(() => {
                observer.disconnect();
                timestampTimeouts.forEach(clearTimeout);
              });
            }
          },
        });
        editorRef.current = mountedEditor;
      } catch {
        if (!cancelled) setLoadError(true);
      }
    }

    void mountEditor();

    return () => {
      cancelled = true;
      cleanupEditorEnhancements.splice(0).forEach((cleanup) => cleanup());
      mountedEditor?.destroy();
      if (editorRef.current === mountedEditor) {
        editorRef.current = null;
      }
    };
  }, [bvid, onSeekTo, recordMarkdownInput, video]);

  useEffect(() => {
    const editor = editorRef.current;
    if (!editor) {
      lastMarkdownRef.current = markdown;
      return;
    }
    const pendingLocalChange = pendingLocalChangeRef.current;
    const isLocalEcho =
      pendingLocalChange !== null &&
      (pendingLocalChange.blocks === blocks ||
        pendingLocalChange.echoMarkdown === markdown ||
        pendingLocalChange.rawMarkdown === markdown);
    if (isLocalEcho) {
      pendingLocalChangeRef.current = null;
      lastMarkdownRef.current = editor.getValue();
      return;
    }
    if (lastMarkdownRef.current === markdown) return;
    if (editor.getValue() !== markdown) {
      editor.setValue(markdown, true);
    }
    lastMarkdownRef.current = markdown;
    pendingLocalChangeRef.current = null;
    undoStackRef.current = [];
    redoStackRef.current = [];
  }, [blocks, markdown]);

  if (loadError) {
    return (
      <div className="video-note-markdown-editor error" role="alert">
        <p>编辑器加载失败，请稍后重试。</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          style={{
            marginTop: "12px",
            padding: "8px 16px",
            borderRadius: "8px",
            border: "1px solid var(--border)",
            background: "var(--paper-2)",
            color: "var(--ink)",
            cursor: "pointer",
          }}
        >
          重新加载页面
        </button>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="video-note-markdown-editor"
      aria-label="Markdown 笔记编辑器"
      onKeyDown={handleKeyDown}
    >
      <div ref={vditorHostRef} id={editorId} className="video-note-vditor" />
    </div>
  );
}
