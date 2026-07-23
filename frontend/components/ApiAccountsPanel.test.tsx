import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ApiAccountsPanel from "@/components/ApiAccountsPanel";
import { apiAccountApi, chatApi, type ApiAccount } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    apiAccountApi: {
      list: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      setDefault: vi.fn(),
      validate: vi.fn(),
      remove: vi.fn(),
    },
    chatApi: {
      ...actual.chatApi,
      getModelConfig: vi.fn(),
    },
  };
});

const deepseekAccount: ApiAccount = {
  id: 7,
  provider: "deepseek",
  provider_label: "DeepSeek",
  display_name: "My DeepSeek",
  base_url: "https://api.deepseek.com/v1",
  model: "deepseek-chat",
  thinking_config: { reasoning: { enabled: true } },
  enabled: true,
  is_default: true,
  configured: true,
  last_validated_at: null,
  last_error: null,
};

const tavilyAccount: ApiAccount = {
  ...deepseekAccount,
  id: 8,
  provider: "tavily",
  provider_label: "Tavily 搜索",
  display_name: "My Tavily",
  base_url: "https://api.tavily.com",
  model: "tavily-search",
  thinking_config: {},
  is_default: false,
};

const modelConfig = {
  current_provider: "deepseek",
  current_api_source: "personal" as const,
  providers: [
    {
      provider: "deepseek",
      label: "DeepSeek",
      enabled: true,
      model: "deepseek-chat",
      thinking_config: {},
      thinking_template: { thinking: { type: "enabled" } },
    },
  ],
};

beforeEach(() => {
  vi.mocked(apiAccountApi.list).mockResolvedValue([]);
  vi.mocked(chatApi.getModelConfig).mockResolvedValue(modelConfig);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("ApiAccountsPanel", () => {
  it("opens on the account list without rendering the editor form", async () => {
    render(<ApiAccountsPanel open onClose={vi.fn()} />);

    expect(await screen.findByText("还没有 AI 服务密钥")).toBeVisible();
    expect(screen.queryByLabelText("API Key")).not.toBeInTheDocument();
    expect(apiAccountApi.list).toHaveBeenCalledOnce();
    expect(chatApi.getModelConfig).toHaveBeenCalledOnce();
  });

  it("opens create in a focused editor and returns to the list without closing", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={onClose} />);

    await screen.findByText("还没有 AI 服务密钥");
    await user.click(screen.getByRole("button", { name: "添加密钥" }));
    expect(screen.getByRole("heading", { name: "添加密钥" })).toBeVisible();
    expect(screen.getByLabelText("API Key")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "返回密钥列表" }));
    expect(screen.getByText("还没有 AI 服务密钥")).toBeVisible();
    expect(screen.queryByLabelText("API Key")).not.toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("opens an existing account in edit mode with provider locked and enabled visible", async () => {
    vi.mocked(apiAccountApi.list).mockResolvedValue([deepseekAccount]);
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={vi.fn()} />);

    await user.click(
      await screen.findByRole("button", { name: /^My DeepSeek/ }),
    );

    expect(screen.getByRole("heading", { name: "编辑密钥" })).toBeVisible();
    expect(screen.getByLabelText("服务商")).toBeDisabled();
    expect(screen.getByLabelText("启用")).toBeChecked();
    expect(screen.getByLabelText("API Key")).toHaveValue("");
  });

  it("updates an existing account without resending an empty key", async () => {
    vi.mocked(apiAccountApi.list).mockResolvedValue([deepseekAccount]);
    vi.mocked(apiAccountApi.update).mockResolvedValue({
      ...deepseekAccount,
      display_name: "Updated DeepSeek",
    });
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={vi.fn()} />);

    await user.click(
      await screen.findByRole("button", { name: /^My DeepSeek/ }),
    );
    await user.clear(screen.getByLabelText("密钥名称"));
    await user.type(screen.getByLabelText("密钥名称"), "Updated DeepSeek");
    await user.click(screen.getByRole("button", { name: "保存修改" }));

    await waitFor(() => expect(apiAccountApi.update).toHaveBeenCalled());
    expect(apiAccountApi.update).toHaveBeenCalledWith(
      7,
      expect.not.objectContaining({ api_key: expect.anything() }),
    );
    expect(apiAccountApi.update).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        display_name: "Updated DeepSeek",
        thinking_config: { reasoning: { enabled: true } },
      }),
    );
    expect(await screen.findByText("AI 服务密钥已更新")).toBeVisible();
    expect(screen.queryByLabelText("API Key")).not.toBeInTheDocument();
  });

  it("creates an account with parsed custom thinking config", async () => {
    vi.mocked(apiAccountApi.create).mockResolvedValue(deepseekAccount);
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={vi.fn()} />);

    await screen.findByText("还没有 AI 服务密钥");
    await user.click(screen.getByRole("button", { name: "添加密钥" }));
    await user.type(screen.getByLabelText("API Key"), "sk-user-secret");
    await user.click(screen.getByRole("tab", { name: "请求配置" }));
    await user.click(screen.getByRole("button", { name: "自定义" }));
    fireEvent.change(
      screen.getByRole("textbox", { name: "请求体 JSON（自定义）" }),
      { target: { value: '{"reasoning":{"effort":"high"}}' } },
    );
    await user.click(
      screen.getByRole("button", { name: "关闭", pressed: false }),
    );
    await user.click(screen.getByRole("button", { name: "标准" }));
    await user.click(screen.getByRole("button", { name: "自定义" }));
    expect(
      screen.getByRole("textbox", { name: "请求体 JSON（自定义）" }),
    ).toHaveValue('{"reasoning":{"effort":"high"}}');
    await user.click(screen.getByRole("button", { name: "添加密钥" }));

    await waitFor(() =>
      expect(apiAccountApi.create).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "deepseek",
          api_key: "sk-user-secret",
          thinking_config: { reasoning: { effort: "high" } },
        }),
      ),
    );
    expect(screen.queryByLabelText("API Key")).not.toBeInTheDocument();
  });

  it("blocks invalid custom JSON and activates the request tab", async () => {
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={vi.fn()} />);

    await screen.findByText("还没有 AI 服务密钥");
    await user.click(screen.getByRole("button", { name: "添加密钥" }));
    await user.type(screen.getByLabelText("API Key"), "sk-user-secret");
    await user.click(screen.getByRole("tab", { name: "请求配置" }));
    await user.click(screen.getByRole("button", { name: "自定义" }));
    fireEvent.change(
      screen.getByRole("textbox", { name: "请求体 JSON（自定义）" }),
      { target: { value: "{bad" } },
    );
    await user.click(screen.getByRole("tab", { name: "基础配置" }));
    await user.click(screen.getByRole("button", { name: "添加密钥" }));

    expect(apiAccountApi.create).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "思考配置 JSON 格式错误",
    );
    expect(screen.getByRole("tab", { name: "请求配置" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("keeps custom mode usable and disables standard when templates fail", async () => {
    vi.mocked(chatApi.getModelConfig).mockRejectedValue(
      new Error("template unavailable"),
    );
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={vi.fn()} />);

    await screen.findByText("还没有 AI 服务密钥");
    await user.click(screen.getByRole("button", { name: "添加密钥" }));
    await user.click(screen.getByRole("tab", { name: "请求配置" }));

    expect(screen.getByRole("button", { name: "标准" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "自定义" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "自定义" }));
    expect(
      screen.getByRole("textbox", { name: "请求体 JSON（自定义）" }),
    ).toBeVisible();
  });

  it("hides request configuration for Tavily", async () => {
    vi.mocked(apiAccountApi.list).mockResolvedValue([tavilyAccount]);
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: /^My Tavily/ }));

    expect(
      screen.queryByRole("tab", { name: "请求配置" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("思考配置")).not.toBeInTheDocument();
  });

  it("keeps set default, validate, and delete inside the single account menu", async () => {
    const nonDefaultAccount = { ...deepseekAccount, is_default: false };
    vi.mocked(apiAccountApi.list).mockResolvedValue([nonDefaultAccount]);
    vi.mocked(apiAccountApi.setDefault).mockResolvedValue(deepseekAccount);
    vi.mocked(apiAccountApi.validate).mockResolvedValue(deepseekAccount);
    vi.mocked(apiAccountApi.remove).mockResolvedValue(undefined);
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true),
    );
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={vi.fn()} />);

    const more = await screen.findByRole("button", {
      name: "更多操作 My DeepSeek",
    });
    expect(more).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "验证" })).toBeNull();

    await user.click(more);
    expect(more).toHaveAttribute("aria-expanded", "true");
    await user.click(screen.getByRole("button", { name: "设默认" }));
    await waitFor(() =>
      expect(apiAccountApi.setDefault).toHaveBeenCalledWith(7),
    );
    expect(more).toHaveAttribute("aria-expanded", "false");

    await user.click(more);
    await user.click(screen.getByRole("button", { name: "验证" }));
    await waitFor(() => expect(apiAccountApi.validate).toHaveBeenCalledWith(7));
    expect(more).toHaveAttribute("aria-expanded", "false");

    await user.click(more);
    await user.click(screen.getByRole("button", { name: "删除" }));
    await waitFor(() => expect(apiAccountApi.remove).toHaveBeenCalledWith(7));
    expect(window.confirm).toHaveBeenCalledWith("删除 My DeepSeek？");
  });
});
