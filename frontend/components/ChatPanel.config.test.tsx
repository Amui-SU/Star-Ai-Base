import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel";
import {
  chatApi,
  cleanupChatPanelTest,
  mockChatPanelDependencies,
} from "@/components/chat/chatPanelTestUtils";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    chatApi: {
      ...actual.chatApi,
      getModelConfig: vi.fn(),
      getWebSearchConfig: vi.fn(),
      health: vi.fn(),
      saveModelProviderConfig: vi.fn(),
      saveWebSearchConfig: vi.fn(),
      setModelProvider: vi.fn(),
      setModelSource: vi.fn(),
    },
    knowledgeBaseApi: {
      ...actual.knowledgeBaseApi,
      stats: vi.fn(),
      getScopeOptions: vi.fn(),
      chatStreamUrl: vi.fn(),
      chat: vi.fn(),
    },
    chatHistoryApi: {
      list: vi.fn(),
      get: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
    },
  };
});

afterEach(cleanupChatPanelTest);

describe("ChatPanel model and service configuration", () => {
  async function openModelConfig(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole("button", { name: "模型选择" }));
    await user.click(screen.getByRole("button", { name: "配置 DeepSeek" }));
  }

  it("does not show the AI key prompt when a model is available", async () => {
    mockChatPanelDependencies();

    render(<ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />);

    expect(await screen.findByText("探索你的收藏")).toBeVisible();
    expect(screen.queryByText("先添加 AI 服务密钥")).toBeNull();
  });

  it("lets users switch between official and personal model sources above the provider list", async () => {
    mockChatPanelDependencies();
    vi.mocked(chatApi.getModelConfig).mockResolvedValue({
      current_provider: "deepseek",
      current_api_source: "official",
      providers: [
        {
          provider: "deepseek",
          label: "DeepSeek",
          enabled: true,
          official_enabled: true,
          personal_enabled: true,
          model: "deepseek-chat",
          thinking_config: {},
          thinking_template: {},
        },
      ],
    });
    const user = userEvent.setup();

    render(<ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />);

    await user.click(await screen.findByLabelText("模型选择"));
    expect(screen.getByRole("button", { name: "官方" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(screen.getByRole("button", { name: "个人" }));

    await waitFor(() =>
      expect(chatApi.setModelSource).toHaveBeenCalledWith("personal"),
    );
    expect(screen.getByRole("button", { name: "个人" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("does not disable the limited official channel before Agnes is configured", async () => {
    mockChatPanelDependencies();
    vi.mocked(chatApi.getModelConfig).mockResolvedValue({
      current_provider: "agnes",
      current_api_source: "personal",
      providers: [
        {
          provider: "agnes",
          label: "Agnes",
          enabled: false,
          official_enabled: false,
          personal_enabled: false,
          model: "agnes-2.0-flash",
          thinking_config: {},
          thinking_template: {},
        },
      ],
    });
    const user = userEvent.setup();

    render(<ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />);

    await user.click(await screen.findByLabelText("模型选择"));
    const officialButton = screen.getByRole("button", { name: "官方" });
    expect(officialButton).toBeEnabled();
    expect(officialButton).toHaveTextContent("限制开放");
  });

  it("treats legacy model config without an explicit source as official", async () => {
    mockChatPanelDependencies();
    vi.mocked(chatApi.getModelConfig).mockResolvedValue({
      current_provider: "deepseek",
      providers: [
        {
          provider: "deepseek",
          label: "DeepSeek",
          enabled: true,
          model: "deepseek-chat",
          thinking_config: {},
          thinking_template: {},
        },
      ],
    });
    const user = userEvent.setup();

    render(<ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />);

    await user.click(await screen.findByLabelText("模型选择"));

    expect(screen.getByRole("button", { name: "官方" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "个人" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("shows the AI key prompt only after config loads with no usable model", async () => {
    mockChatPanelDependencies();
    vi.mocked(chatApi.getModelConfig).mockResolvedValue({
      current_provider: "deepseek",
      current_api_source: "personal",
      providers: [
        {
          provider: "deepseek",
          label: "DeepSeek",
          enabled: false,
          model: "deepseek-chat",
          thinking_config: {},
          thinking_template: {},
        },
      ],
    });
    const onOpenApiAccounts = vi.fn();

    render(
      <ChatPanel
        knowledgeBaseId={1}
        knowledgeBaseName="Test KB"
        onOpenApiAccounts={onOpenApiAccounts}
      />,
    );

    expect(await screen.findByText("先添加 AI 服务密钥")).toBeVisible();
    expect(screen.getByRole("button", { name: "配置密钥" })).toBeVisible();
  });

  it("places the knowledge-base meta next to the model selector", async () => {
    mockChatPanelDependencies();

    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );

    expect(await screen.findByText("Test KB")).toBeVisible();
    const contextActions = container.querySelector(".chat-context-actions");
    expect(contextActions).toHaveTextContent("Test KB");
    expect(contextActions?.querySelector(".chat-kb-meta")).toHaveTextContent(
      "1 个视频",
    );
    expect(contextActions?.querySelector(".model-status-card")).not.toBeNull();
  });

  it("saves parsed custom thinking JSON from the request tab", async () => {
    mockChatPanelDependencies();
    vi.mocked(chatApi.saveModelProviderConfig).mockResolvedValue({
      ok: true,
      current_provider: "deepseek",
      model: "deepseek-v4-pro",
      provider_label: "DeepSeek",
      thinking_config: { reasoning: { enabled: true } },
      thinking_template: { thinking: { type: "enabled" } },
      verified: true,
      latency_ms: 18,
    });
    const user = userEvent.setup();

    render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" isAdmin />,
    );
    await openModelConfig(user);

    expect(screen.getByRole("tab", { name: "基础配置" })).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "请求配置" }));
    await user.click(screen.getByRole("button", { name: "自定义" }));
    const editor = screen.getByRole("textbox", {
      name: "请求体 JSON（自定义）",
    });
    fireEvent.change(editor, {
      target: { value: '{"reasoning":{"enabled":true}}' },
    });
    await user.click(screen.getByRole("button", { name: "保存配置" }));

    await waitFor(() =>
      expect(chatApi.saveModelProviderConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "deepseek",
          thinking_mode: "custom",
          thinking_config: { reasoning: { enabled: true } },
        }),
      ),
    );
  });

  it("blocks invalid custom JSON and returns to the request tab", async () => {
    mockChatPanelDependencies();
    const user = userEvent.setup();

    render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" isAdmin />,
    );
    await openModelConfig(user);
    await user.click(screen.getByRole("tab", { name: "请求配置" }));
    await user.click(screen.getByRole("button", { name: "自定义" }));
    const editor = screen.getByRole("textbox", {
      name: "请求体 JSON（自定义）",
    });
    fireEvent.change(editor, { target: { value: "{bad" } });
    await user.click(screen.getByRole("tab", { name: "基础配置" }));
    await user.click(screen.getByRole("button", { name: "保存配置" }));

    expect(chatApi.saveModelProviderConfig).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "思考配置 JSON 格式错误",
    );
    expect(screen.getByRole("tab", { name: "请求配置" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("preserves the custom JSON draft while switching thinking modes", async () => {
    mockChatPanelDependencies();
    const user = userEvent.setup();

    render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" isAdmin />,
    );
    await openModelConfig(user);
    await user.click(screen.getByRole("tab", { name: "请求配置" }));
    await user.click(screen.getByRole("button", { name: "自定义" }));
    const editor = screen.getByRole("textbox", {
      name: "请求体 JSON（自定义）",
    });
    fireEvent.change(editor, { target: { value: '{"draft":"kept"}' } });
    await user.click(
      screen.getByRole("button", { name: "关闭", pressed: false }),
    );
    await user.click(screen.getByRole("button", { name: "标准" }));
    await user.click(screen.getByRole("button", { name: "自定义" }));

    expect(
      screen.getByRole("textbox", { name: "请求体 JSON（自定义）" }),
    ).toHaveValue('{"draft":"kept"}');
  });

  it("hides global provider and Tavily configuration controls from regular users", async () => {
    mockChatPanelDependencies();
    vi.mocked(chatApi.getModelConfig).mockResolvedValue({
      current_provider: "deepseek",
      providers: [
        {
          provider: "deepseek",
          label: "DeepSeek",
          enabled: true,
          model: "deepseek-v4-pro",
          thinking_config: {},
          thinking_template: {},
        },
        {
          provider: "kimi",
          label: "Moonshot Kimi",
          enabled: false,
          model: "moonshot-v1-8k",
          thinking_config: {},
          thinking_template: {},
        },
      ],
    });

    const user = userEvent.setup();
    render(<ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />);

    await user.click(await screen.findByRole("button", { name: "模型选择" }));
    expect(screen.queryByRole("button", { name: "配置 DeepSeek" })).toBeNull();
    expect(screen.getByText("Moonshot Kimi")).toBeVisible();

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    await user.click(screen.getByRole("button", { name: "联网搜索" }));
    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    const tavilyButton = await screen.findByRole("button", { name: "Tavily" });

    expect(tavilyButton).toBeDisabled();
    expect(screen.queryByRole("button", { name: "配置 Tavily" })).toBeNull();
    expect(screen.getByText("Tavily 需要管理员配置")).toBeVisible();
  });

  it("lets regular users open their own AI service key settings for Tavily", async () => {
    mockChatPanelDependencies();
    vi.mocked(chatApi.getWebSearchConfig).mockResolvedValue({
      provider: "auto",
      tavily_configured: false,
      fallback_html: true,
      tavily_search_depth: "basic",
    });
    const onOpenApiAccounts = vi.fn();
    const user = userEvent.setup();

    const { container } = render(
      <ChatPanel
        knowledgeBaseId={1}
        knowledgeBaseName="Test KB"
        onOpenApiAccounts={onOpenApiAccounts}
      />,
    );

    await screen.findByText("Test KB");
    const scopeTrigger = container.querySelector(".scope-picker-trigger");
    expect(scopeTrigger).not.toBeNull();
    await user.click(scopeTrigger as HTMLElement);
    const webSearchButton = container.querySelector(".scope-web-search-btn");
    expect(webSearchButton).not.toBeNull();
    await user.click(webSearchButton as HTMLElement);
    await user.click(scopeTrigger as HTMLElement);
    const tavilyButton = await screen.findByRole("button", { name: "Tavily" });

    expect(tavilyButton).not.toBeDisabled();
    await user.click(tavilyButton);
    expect(onOpenApiAccounts).toHaveBeenCalled();
  });
});
