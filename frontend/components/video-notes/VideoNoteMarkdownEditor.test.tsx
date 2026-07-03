import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { VideoNoteBlock } from "@/lib/api";
import VideoNoteMarkdownEditor from "./VideoNoteMarkdownEditor";

interface MockVditorOptions {
  after?: () => void;
  height?: string;
  input?: (value: string) => void;
  mode?: string;
  value?: string;
}

const vditorState = vi.hoisted(() => ({
  instances: [] as Array<{
    destroyed: boolean;
    element: HTMLTextAreaElement;
    getValue: () => string;
    nativeElement: HTMLDivElement;
    options: MockVditorOptions;
    setValue: (value: string, clearStack?: boolean) => void;
    setValueCalls: Array<{ clearStack?: boolean; value: string }>;
    target: string | HTMLElement;
  }>,
}));

vi.mock("vditor", () => ({
  default: class MockVditor {
    destroyed = false;
    element: HTMLTextAreaElement;
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
      this.element.addEventListener("input", () => {
        options.input?.(this.element.value);
      });
      const host =
        typeof target === "string" ? document.getElementById(target) : target;
      host?.append(this.element, this.nativeElement);
      vditorState.instances.push(this);
      window.setTimeout(() => options.after?.(), 0);
    }

    getValue() {
      return this.element.value;
    }

    setValue(value: string, clearStack?: boolean) {
      this.setValueCalls.push({ clearStack, value });
      this.element.value = value;
      this.element.scrollTop = 0;
    }

    destroy() {
      this.destroyed = true;
      this.element.remove();
      this.nativeElement.remove();
    }
  },
}));

const initialBlocks: VideoNoteBlock[] = [
  { id: "h1", type: "heading", level: 1, text: "Original title" },
  { id: "p1", type: "paragraph", text: "Original body" },
];

function StatefulMarkdownEditor() {
  const [blocks, setBlocks] = useState(initialBlocks);
  return <VideoNoteMarkdownEditor blocks={blocks} onChange={setBlocks} />;
}

afterEach(() => {
  cleanup();
  vditorState.instances.length = 0;
});

describe("VideoNoteMarkdownEditor", () => {
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
