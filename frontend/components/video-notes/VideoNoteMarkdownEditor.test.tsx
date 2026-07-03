import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { VideoNoteBlock } from "@/lib/api";
import VideoNoteMarkdownEditor from "./VideoNoteMarkdownEditor";

interface MockVditorOptions {
  after?: () => void;
  input?: (value: string) => void;
  mode?: string;
  value?: string;
}

const vditorState = vi.hoisted(() => ({
  instances: [] as Array<{
    destroyed: boolean;
    element: HTMLTextAreaElement;
    getValue: () => string;
    options: MockVditorOptions;
    setValue: (value: string) => void;
  }>,
}));

vi.mock("vditor", () => ({
  default: class MockVditor {
    destroyed = false;
    element: HTMLTextAreaElement;
    options: MockVditorOptions;

    constructor(id: string, options: MockVditorOptions) {
      this.options = options;
      this.element = document.createElement("textarea");
      this.element.setAttribute("aria-label", "Vditor mock editor");
      this.element.value = options.value ?? "";
      this.element.addEventListener("input", () => {
        options.input?.(this.element.value);
      });
      document.getElementById(id)?.append(this.element);
      vditorState.instances.push(this);
      window.setTimeout(() => options.after?.(), 0);
    }

    getValue() {
      return this.element.value;
    }

    setValue(value: string) {
      this.element.value = value;
    }

    destroy() {
      this.destroyed = true;
      this.element.remove();
    }
  },
}));

const initialBlocks: VideoNoteBlock[] = [
  { id: "h1", type: "heading", level: 1, text: "Original title" },
  { id: "p1", type: "paragraph", text: "Original body" },
];

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
});
