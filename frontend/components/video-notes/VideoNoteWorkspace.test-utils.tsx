import type { ComponentProps } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import VideoNoteWorkspace from "./VideoNoteWorkspace";
import type { VideoNote } from "@/lib/api";

const videoNoteApi = vi.hoisted(() => ({
  list: vi.fn(),
  detail: vi.fn(),
  create: vi.fn(),
  save: vi.fn(),
  exportMarkdown: vi.fn(),
  generateSummary: vi.fn(),
  aiEdit: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    videoNoteApi,
  };
});

interface MockVditorOptions {
  i18n?: Record<string, string>;
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

    constructor(target: string | HTMLElement, options: MockVditorOptions) {
      this.options = options;
      this.element = document.createElement("textarea");
      this.element.setAttribute("aria-label", "Vditor mock editor");
      this.element.value = options.value ?? "";
      this.element.addEventListener("input", () => {
        options.input?.(this.element.value);
      });
      const host =
        typeof target === "string" ? document.getElementById(target) : target;
      host?.append(this.element);
      vditorState.instances.push(this);
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

vi.mock("vditor/dist/js/i18n/zh_CN.js", () => {
  window.VditorI18n = {
    headings: "标题",
  } as unknown as typeof window.VditorI18n;
  return {};
});

export async function findMarkdownEditor() {
  return (await screen.findByLabelText(
    "Vditor mock editor",
  )) as HTMLTextAreaElement;
}

export const baseNote: VideoNote = {
  id: 9,
  user_id: 1,
  workspace_id: 1,
  knowledge_base_id: 7,
  bvid: "BVNOTE123",
  title: "AI 视频学习法",
  template_id: "standard",
  blocks: [
    { id: "h1", type: "heading", level: 1, text: "AI 视频学习法" },
    { id: "p1", type: "paragraph", text: "旧内容" },
  ],
  tags: ["AI"],
  summary_status: "seeded",
  created_at: "2026-07-02T00:00:00Z",
  updated_at: "2026-07-02T00:00:00Z",
  video: null,
};

export const video = {
  bvid: "BVNOTE123",
  title: "AI 视频学习法",
  folder_title: "学习收藏夹",
  owner_name: "知识区 UP",
  url: "https://www.bilibili.com/video/BVNOTE123",
};

export function renderWorkspace(
  props: Partial<ComponentProps<typeof VideoNoteWorkspace>> = {},
) {
  return render(
    <VideoNoteWorkspace
      knowledgeBaseId={7}
      autosaveDelayMs={2000}
      {...props}
    />,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
  vditorState.instances.length = 0;
});

export { videoNoteApi, vditorState };
