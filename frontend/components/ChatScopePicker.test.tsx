import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatScopePicker from "@/components/ChatScopePicker";
import type { WebSearchProvider } from "@/lib/api";
import type { ChatScopeSelection } from "@/lib/chatScope";

afterEach(() => {
  cleanup();
});

const options = {
  folders: [
    {
      media_id: 101,
      title: "AI 课程",
      video_count: 2,
      videos: [
        { bvid: "BV1", title: "RAG 入门" },
        { bvid: "BV2", title: "评估方法" },
      ],
    },
    {
      media_id: 202,
      title: "空收藏夹",
      video_count: 0,
      videos: [],
    },
  ],
};

function ControlledPicker({
  initialValue = { folderIds: [], bvids: [] },
  onChange,
  webSearchEnabled = false,
  onWebSearchChange,
  webSearchProvider = "auto",
  onWebSearchProviderChange,
  tavilyConfigured = false,
  onConfigureTavily,
  webSearchNotice = "",
  disabled = false,
}: {
  initialValue?: ChatScopeSelection;
  onChange?: (next: ChatScopeSelection) => void;
  webSearchEnabled?: boolean;
  onWebSearchChange?: (enabled: boolean) => void;
  webSearchProvider?: WebSearchProvider;
  onWebSearchProviderChange?: (provider: WebSearchProvider) => void;
  tavilyConfigured?: boolean;
  onConfigureTavily?: () => void;
  webSearchNotice?: string;
  disabled?: boolean;
}) {
  const [value, setValue] = useState(initialValue);
  const [webSearch, setWebSearch] = useState(webSearchEnabled);
  const [provider, setProvider] =
    useState<WebSearchProvider>(webSearchProvider);
  return (
    <ChatScopePicker
      options={options}
      value={value}
      webSearchEnabled={webSearch}
      webSearchProvider={provider}
      tavilyConfigured={tavilyConfigured}
      webSearchNotice={webSearchNotice}
      disabled={disabled}
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
      onWebSearchChange={(enabled) => {
        setWebSearch(enabled);
        onWebSearchChange?.(enabled);
      }}
      onWebSearchProviderChange={(nextProvider) => {
        setProvider(nextProvider);
        onWebSearchProviderChange?.(nextProvider);
      }}
      onConfigureTavily={onConfigureTavily ?? vi.fn()}
    />
  );
}

describe("ChatScopePicker", () => {
  it("selects folders and videos independently across controlled updates", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ControlledPicker onChange={onChange} />);

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    await user.click(screen.getByRole("checkbox", { name: "AI 课程" }));
    expect(onChange).toHaveBeenLastCalledWith({
      folderIds: [101],
      bvids: [],
    });

    await user.click(screen.getByRole("checkbox", { name: "RAG 入门" }));
    expect(onChange).toHaveBeenLastCalledWith({
      folderIds: [101],
      bvids: ["BV1"],
    });
  });

  it("resets to the whole knowledge base", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ControlledPicker
        initialValue={{ folderIds: [101], bvids: ["BV1"] }}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    await user.click(screen.getByRole("button", { name: "整个知识库" }));

    expect(onChange).toHaveBeenLastCalledWith({ folderIds: [], bvids: [] });
    expect(
      screen.getByRole("button", { name: /^提问范围/ }),
    ).toHaveAccessibleName("提问范围：整个知识库");
  });

  it("toggles web search from the picker menu", async () => {
    const user = userEvent.setup();
    const onWebSearchChange = vi.fn();
    render(<ControlledPicker onWebSearchChange={onWebSearchChange} />);

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    await user.click(screen.getByRole("button", { name: "联网搜索" }));

    expect(onWebSearchChange).toHaveBeenLastCalledWith(true);
    expect(
      screen.getByRole("button", { name: /^提问范围/ }),
    ).toHaveAccessibleName("提问范围：整个知识库，联网搜索已开启");
  });

  it("shows a privacy hint on the web search control without splitting the UI", async () => {
    const user = userEvent.setup();
    render(<ControlledPicker />);

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));

    expect(screen.getByRole("button", { name: "联网搜索" })).toHaveAttribute(
      "title",
      "开启后，模型可能向外部搜索服务发送查询并读取公开网页",
    );
  });

  it("lets enabled web search choose Tavily and open configuration inline", async () => {
    const user = userEvent.setup();
    const onWebSearchProviderChange = vi.fn();
    const onConfigureTavily = vi.fn();
    render(
      <ControlledPicker
        webSearchEnabled
        tavilyConfigured={false}
        onWebSearchProviderChange={onWebSearchProviderChange}
        onConfigureTavily={onConfigureTavily}
      />,
    );

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    await user.click(screen.getByRole("button", { name: "Tavily" }));

    expect(onWebSearchProviderChange).toHaveBeenLastCalledWith("tavily");
    await user.click(screen.getByRole("button", { name: "配置 Tavily" }));
    expect(onConfigureTavily).toHaveBeenCalled();
  });

  it("uses the temporary web search notice before restoring the scope summary", () => {
    const { rerender } = render(
      <ControlledPicker webSearchEnabled webSearchNotice="联网搜索已开启" />,
    );

    const trigger = screen.getByRole("button", { name: /^提问范围/ });
    expect(trigger).toHaveTextContent("联网搜索已开启");
    expect(trigger).toHaveAccessibleName(
      "提问范围：整个知识库，联网搜索已开启",
    );

    rerender(<ControlledPicker webSearchEnabled webSearchNotice="" />);

    expect(trigger).toHaveTextContent("整个知识库");
    expect(trigger).not.toHaveTextContent("联网搜索已开启");
    expect(trigger).toHaveAccessibleName(
      "提问范围：整个知识库，联网搜索已开启",
    );
  });

  it("filters standalone videos by title and bvid", async () => {
    const user = userEvent.setup();
    render(<ControlledPicker />);

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    await user.type(screen.getByRole("textbox", { name: "搜索视频" }), "BV2");

    const list = screen.getByText("单独选择视频").closest(".scope-section");
    expect(list).not.toBeNull();
    expect(
      within(list as HTMLElement).getByRole("checkbox", { name: "评估方法" }),
    ).toBeInTheDocument();
    expect(
      within(list as HTMLElement).queryByRole("checkbox", { name: "RAG 入门" }),
    ).not.toBeInTheDocument();
  });

  it("deduplicates videos that appear in multiple folders", async () => {
    const user = userEvent.setup();
    const duplicatedOptions = {
      folders: [
        options.folders[0],
        {
          media_id: 303,
          title: "重复收藏夹",
          video_count: 1,
          videos: [{ bvid: "BV1", title: "RAG 入门" }],
        },
      ],
    };

    render(
      <ChatScopePicker
        options={duplicatedOptions}
        value={{ folderIds: [], bvids: [] }}
        webSearchEnabled={false}
        onChange={vi.fn()}
        onWebSearchChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));

    const list = screen.getByText("单独选择视频").closest(".scope-section");
    expect(list).not.toBeNull();
    expect(
      within(list as HTMLElement).getAllByRole("checkbox", {
        name: "RAG 入门",
      }),
    ).toHaveLength(1);
  });

  it("closes on Escape and outside click", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <button type="button">外部按钮</button>
        <ControlledPicker />
      </div>,
    );

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    expect(
      screen.getByRole("dialog", { name: "提问范围" }),
    ).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("dialog", { name: "提问范围" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    await user.click(screen.getByRole("button", { name: "外部按钮" }));
    expect(
      screen.queryByRole("dialog", { name: "提问范围" }),
    ).not.toBeInTheDocument();
  });

  it("does not open when disabled", async () => {
    const user = userEvent.setup();
    render(<ControlledPicker disabled />);

    const trigger = screen.getByRole("button", { name: /^提问范围/ });
    expect(trigger).toBeDisabled();
    await user.click(trigger);
    expect(
      screen.queryByRole("dialog", { name: "提问范围" }),
    ).not.toBeInTheDocument();
  });
});
