import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { VideoNoteBlock, VideoNoteVideo } from "@/lib/api";
import VideoNoteMarkdownEditor, {
  buildBilibiliTimestampUrl,
} from "./VideoNoteMarkdownEditor";

interface MockVditorOptions {
  after?: () => void;
  height?: string;
  input?: (value: string) => void;
  mode?: string;
  value?: string;
}

const vditorState = vi.hoisted(() => ({
  instances: [] as Array<{
    afterRan: boolean;
    destroyed: boolean;
    element: HTMLTextAreaElement;
    getValue: () => string;
    irElement: HTMLDivElement;
    nativeElement: HTMLDivElement;
    options: MockVditorOptions;
    runAfter: () => void;
    setValue: (value: string, clearStack?: boolean) => void;
    setValueCalls: Array<{ clearStack?: boolean; value: string }>;
    target: string | HTMLElement;
  }>,
}));

vi.mock("vditor", () => ({
  default: class MockVditor {
    afterRan = false;
    destroyed = false;
    element: HTMLTextAreaElement;
    irElement: HTMLDivElement;
    nativeElement: HTMLDivElement;
    options: MockVditorOptions;
    setValueCalls: Array<{ clearStack?: boolean; value: string }> = [];

    target: string | HTMLElement;

    constructor(target: string | HTMLElement, options: MockVditorOptions) {
      this.target = target;
      this.options = options;
      this.element = document.createElement("textarea");
      this.element.setAttribute("aria-label", "Vditor mock editor");
      this.element.value = options.value ?? "";
      this.nativeElement = document.createElement("div");
      this.nativeElement.setAttribute("data-testid", "vditor-native-input");
      this.irElement = document.createElement("div");
      this.irElement.className = "vditor-ir";
      this.irElement.setAttribute("data-testid", "vditor-ir");
      this.element.addEventListener("input", () => {
        options.input?.(this.element.value);
      });
      const host =
        typeof target === "string" ? document.getElementById(target) : target;
      host?.append(this.element, this.nativeElement, this.irElement);
      vditorState.instances.push(this);
      window.setTimeout(this.runAfter, 0);
    }

    getValue() {
      return this.element.value;
    }

    runAfter = () => {
      if (this.afterRan) return;
      this.afterRan = true;
      this.options.after?.();
    };

    setValue(value: string, clearStack?: boolean) {
      this.setValueCalls.push({ clearStack, value });
      this.element.value = value;
      this.element.scrollTop = 0;
    }

    destroy() {
      this.destroyed = true;
      this.element.remove();
      this.nativeElement.remove();
      this.irElement.remove();
    }
  },
}));

const initialBlocks: VideoNoteBlock[] = [
  { id: "h1", type: "heading", level: 1, text: "Original title" },
  { id: "p1", type: "paragraph", text: "Original body" },
];

function mockCaretRangeFromPoint(range: Range) {
  const documentWithCaret = document as Document & {
    caretRangeFromPoint?: (x: number, y: number) => Range | null;
  };
  const originalCaretRangeFromPoint = documentWithCaret.caretRangeFromPoint;
  documentWithCaret.caretRangeFromPoint = vi.fn(() => range);

  return () => {
    if (originalCaretRangeFromPoint) {
      documentWithCaret.caretRangeFromPoint = originalCaretRangeFromPoint;
    } else {
      delete documentWithCaret.caretRangeFromPoint;
    }
  };
}

function StatefulMarkdownEditor() {
  const [blocks, setBlocks] = useState(initialBlocks);
  return <VideoNoteMarkdownEditor blocks={blocks} onChange={setBlocks} />;
}

afterEach(() => {
  cleanup();
  vditorState.instances.length = 0;
});

describe("VideoNoteMarkdownEditor", () => {
  it("builds multipart timestamp URLs with the current page and part-relative seconds", () => {
    const video: VideoNoteVideo = {
      bvid: "BV1xx411x7xx",
      title: "合集视频 P2/4",
      url: "https://www.bilibili.com/video/BV1xx411x7xx",
      parts: [{ page: 2, cid: 222, part: "第二讲", duration: 540 }],
    };

    expect(buildBilibiliTimestampUrl("BV1xx411x7xx", 83, video)).toBe(
      "https://www.bilibili.com/video/BV1xx411x7xx?p=2&t=83",
    );
  });

  it("does not open a bare URL when clicking blank space on its containing line", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    render(
      <VideoNoteMarkdownEditor blocks={initialBlocks} onChange={vi.fn()} />,
    );

    await screen.findByLabelText("Vditor mock editor");
    const instance = vditorState.instances[0];
    const lineText = "查看 https://example.com/notes 后续文字";
    const paragraph = document.createElement("p");
    const textNode = document.createTextNode(lineText);
    paragraph.append(textNode);
    instance.irElement.append(paragraph);
    instance.runAfter();

    const range = document.createRange();
    range.setStart(textNode, lineText.length);
    range.setEnd(textNode, lineText.length);
    const restoreCaretRangeFromPoint = mockCaretRangeFromPoint(range);

    try {
      fireEvent.click(paragraph, { clientX: 999, clientY: 12 });

      expect(openSpy).not.toHaveBeenCalled();
    } finally {
      restoreCaretRangeFromPoint();
      openSpy.mockRestore();
    }
  });

  it("opens a bare URL when the click lands on the URL text", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    render(
      <VideoNoteMarkdownEditor blocks={initialBlocks} onChange={vi.fn()} />,
    );

    await screen.findByLabelText("Vditor mock editor");
    const instance = vditorState.instances[0];
    const lineText = "查看 https://example.com/notes 后续文字";
    const paragraph = document.createElement("p");
    const textNode = document.createTextNode(lineText);
    paragraph.append(textNode);
    instance.irElement.append(paragraph);
    instance.runAfter();

    const range = document.createRange();
    range.setStart(textNode, lineText.indexOf("example"));
    range.setEnd(textNode, lineText.indexOf("example"));
    const restoreCaretRangeFromPoint = mockCaretRangeFromPoint(range);

    try {
      fireEvent.click(paragraph, { clientX: 120, clientY: 12 });

      expect(openSpy).toHaveBeenCalledWith(
        "https://example.com/notes",
        "_blank",
        "noopener,noreferrer",
      );
    } finally {
      restoreCaretRangeFromPoint();
      openSpy.mockRestore();
    }
  });

  it("marks bare URL text as its own clickable cursor target", async () => {
    render(
      <VideoNoteMarkdownEditor blocks={initialBlocks} onChange={vi.fn()} />,
    );

    await screen.findByLabelText("Vditor mock editor");
    const instance = vditorState.instances[0];
    const lineText = "查看 https://example.com/notes 后续文字";
    const paragraph = document.createElement("p");
    paragraph.textContent = lineText;
    instance.irElement.append(paragraph);
    instance.runAfter();

    await waitFor(() =>
      expect(paragraph.querySelector(".video-plain-url-link")).not.toBeNull(),
    );
    const urlTarget = paragraph.querySelector(".video-plain-url-link");

    expect(urlTarget).toHaveTextContent("https://example.com/notes");
    expect(urlTarget).toHaveAttribute("data-url", "https://example.com/notes");
    expect(paragraph.textContent).toBe(lineText);
  });

  it("opens a hidden Markdown link only from the anchor text", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    render(
      <VideoNoteMarkdownEditor blocks={initialBlocks} onChange={vi.fn()} />,
    );

    await screen.findByLabelText("Vditor mock editor");
    const instance = vditorState.instances[0];
    const paragraph = document.createElement("p");
    const anchor = document.createElement("a");
    anchor.href = "https://example.com/hidden";
    anchor.textContent = "隐藏链接";
    paragraph.append("前缀 ", anchor, " 后续空白");
    instance.irElement.append(paragraph);
    instance.runAfter();

    fireEvent.click(paragraph);
    expect(openSpy).not.toHaveBeenCalled();

    fireEvent.click(anchor);
    expect(openSpy).toHaveBeenCalledWith(
      "https://example.com/hidden",
      "_blank",
      "noopener,noreferrer",
    );

    openSpy.mockRestore();
  });

  it("initializes Vditor in instant-render Markdown mode with block content", async () => {
    render(
      <VideoNoteMarkdownEditor blocks={initialBlocks} onChange={vi.fn()} />,
    );

    const editor = await screen.findByLabelText("Vditor mock editor");
    await waitFor(() => expect(vditorState.instances).toHaveLength(1));

    expect(vditorState.instances[0].options.mode).toBe("ir");
    expect(vditorState.instances[0].options.height).toBe("auto");
    expect(vditorState.instances[0].target).toBeInstanceOf(HTMLElement);
    expect(editor).toHaveValue("# Original title\n\nOriginal body");
  });

  it("emits parsed blocks when Markdown content changes", async () => {
    const onChange = vi.fn();
    render(
      <VideoNoteMarkdownEditor blocks={initialBlocks} onChange={onChange} />,
    );

    const editor = await screen.findByLabelText("Vditor mock editor");
    fireEvent.input(editor, {
      target: { value: "# Updated title\n\nUpdated body" },
    });

    await waitFor(() =>
      expect(onChange).toHaveBeenLastCalledWith([
        { id: "h1", type: "heading", level: 1, text: "Updated title" },
        { id: "p1", type: "paragraph", text: "Updated body" },
      ]),
    );
  });

  it("syncs external block changes from AI edits into the mounted editor", async () => {
    const { rerender } = render(
      <VideoNoteMarkdownEditor blocks={initialBlocks} onChange={vi.fn()} />,
    );

    const editor = await screen.findByLabelText("Vditor mock editor");

    rerender(
      <VideoNoteMarkdownEditor
        blocks={[{ id: "p1", type: "ai_summary", text: "AI summary text" }]}
        onChange={vi.fn()}
      />,
    );

    await waitFor(() => expect(editor).toHaveValue("AI summary text"));
  });

  it("supports keyboard undo and redo for user edits", async () => {
    const onChange = vi.fn();
    render(
      <VideoNoteMarkdownEditor blocks={initialBlocks} onChange={onChange} />,
    );

    const editor = await screen.findByLabelText("Vditor mock editor");
    fireEvent.input(editor, {
      target: { value: "# Updated title\n\nUpdated body" },
    });
    await waitFor(() =>
      expect(onChange).toHaveBeenLastCalledWith([
        { id: "h1", type: "heading", level: 1, text: "Updated title" },
        { id: "p1", type: "paragraph", text: "Updated body" },
      ]),
    );

    fireEvent.keyDown(editor, { key: "z", ctrlKey: true });
    await waitFor(() =>
      expect(editor).toHaveValue("# Original title\n\nOriginal body"),
    );
    expect(onChange).toHaveBeenLastCalledWith(initialBlocks);

    fireEvent.keyDown(editor, { key: "y", ctrlKey: true });
    await waitFor(() =>
      expect(editor).toHaveValue("# Updated title\n\nUpdated body"),
    );
    expect(onChange).toHaveBeenLastCalledWith([
      { id: "h1", type: "heading", level: 1, text: "Updated title" },
      { id: "p1", type: "paragraph", text: "Updated body" },
    ]);
  });

  it("does not reset scroll when parent state echoes normalized local input", async () => {
    render(<StatefulMarkdownEditor />);

    const editor = await screen.findByLabelText("Vditor mock editor");
    const localMarkdown = "# Updated title   \n\nUpdated body\n\n";
    editor.scrollTop = 160;

    fireEvent.input(editor, { target: { value: localMarkdown } });

    await waitFor(() => expect(editor).toHaveValue(localMarkdown));
    expect(vditorState.instances[0].setValueCalls).toEqual([]);
    expect(editor.scrollTop).toBe(160);
  });

  it("keeps keyboard undo and redo available after parent state echoes local input", async () => {
    render(<StatefulMarkdownEditor />);

    const editor = await screen.findByLabelText("Vditor mock editor");
    const localMarkdown = "# Updated title   \n\nUpdated body\n\n";

    fireEvent.input(editor, { target: { value: localMarkdown } });
    await waitFor(() => expect(editor).toHaveValue(localMarkdown));

    fireEvent.keyDown(editor, { key: "z", ctrlKey: true });
    await waitFor(() =>
      expect(editor).toHaveValue("# Original title\n\nOriginal body"),
    );

    fireEvent.keyDown(editor, { key: "y", ctrlKey: true });
    await waitFor(() => expect(editor).toHaveValue(localMarkdown));
  });

  it("lets Vditor handle native undo when local history is empty", async () => {
    render(
      <VideoNoteMarkdownEditor blocks={initialBlocks} onChange={vi.fn()} />,
    );

    const editor = await screen.findByLabelText("Vditor mock editor");
    const event = new KeyboardEvent("keydown", {
      bubbles: true,
      cancelable: true,
      ctrlKey: true,
      key: "z",
    });

    editor.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(false);
  });

  it("tracks native Vditor DOM input for keyboard undo", async () => {
    const onChange = vi.fn();
    render(
      <VideoNoteMarkdownEditor blocks={initialBlocks} onChange={onChange} />,
    );

    await screen.findByLabelText("Vditor mock editor");
    const instance = vditorState.instances[0];
    instance.element.value = "# Native title\n\nNative body";
    fireEvent.input(instance.nativeElement);

    await waitFor(() =>
      expect(onChange).toHaveBeenLastCalledWith([
        { id: "h1", type: "heading", level: 1, text: "Native title" },
        { id: "p1", type: "paragraph", text: "Native body" },
      ]),
    );

    fireEvent.keyDown(instance.nativeElement, { key: "z", ctrlKey: true });

    await waitFor(() =>
      expect(instance.element).toHaveValue("# Original title\n\nOriginal body"),
    );
    expect(onChange).toHaveBeenLastCalledWith(initialBlocks);
  });

  it("captures a pending Vditor value before keyboard undo", async () => {
    const onChange = vi.fn();
    render(
      <VideoNoteMarkdownEditor blocks={initialBlocks} onChange={onChange} />,
    );

    await screen.findByLabelText("Vditor mock editor");
    const instance = vditorState.instances[0];
    instance.element.value = "# Pending title\n\nPending body";

    fireEvent.keyDown(instance.nativeElement, { key: "z", ctrlKey: true });

    await waitFor(() =>
      expect(instance.element).toHaveValue("# Original title\n\nOriginal body"),
    );
    expect(onChange).toHaveBeenNthCalledWith(1, [
      { id: "h1", type: "heading", level: 1, text: "Pending title" },
      { id: "p1", type: "paragraph", text: "Pending body" },
    ]);
    expect(onChange).toHaveBeenLastCalledWith(initialBlocks);
  });
});
