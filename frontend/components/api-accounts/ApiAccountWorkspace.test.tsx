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
import { apiAccountApi, chatApi } from "@/lib/api";

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
      validateDraft: vi.fn(),
      remove: vi.fn(),
    },
    chatApi: { ...actual.chatApi, getModelConfig: vi.fn() },
  };
});

beforeEach(() => {
  vi.mocked(apiAccountApi.list).mockResolvedValue([]);
  vi.mocked(chatApi.getModelConfig).mockResolvedValue({
    current_provider: "deepseek",
    current_api_source: "personal",
    providers: [],
  });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

function mockViewport(mobile: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: mobile && query === "(max-width: 720px)",
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

async function openCreate() {
  const user = userEvent.setup();
  render(<ApiAccountsPanel open onClose={vi.fn()} />);
  await screen.findByText("还没有 AI 服务密钥");
  await user.click(screen.getByRole("button", { name: "添加密钥" }));
  return user;
}

describe("ApiAccountWorkspace", () => {
  it.each(['{"version":1,"fallback_model":"raw-only"}', "{invalid"])(
    "protects unapplied raw JSON before requests and navigation: %s",
    async (rawValue) => {
      const confirm = vi.fn(() => false);
      vi.stubGlobal("confirm", confirm);
      const user = await openCreate();
      await user.click(screen.getByRole("button", { name: "配置 JSON" }));
      fireEvent.change(screen.getByLabelText("完整 advanced_config JSON"), {
        target: { value: rawValue },
      });

      expect(screen.getByText("未保存")).toBeVisible();
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(true);
      await user.click(screen.getByRole("button", { name: "返回密钥列表" }));
      expect(confirm).toHaveBeenCalledWith("当前配置尚未保存，确认离开？");
      expect(
        screen.getByRole("dialog", { name: "添加 API 密钥" }),
      ).toBeVisible();
      await user.type(screen.getByLabelText("API Key"), "draft-secret");
      await user.click(screen.getByRole("button", { name: "保存配置" }));
      await user.click(screen.getByRole("button", { name: "测试连接" }));
      expect(apiAccountApi.create).not.toHaveBeenCalled();
      expect(apiAccountApi.validateDraft).not.toHaveBeenCalled();
      expect(screen.getByRole("alert")).toHaveTextContent("请先应用 JSON 配置");
      expect(screen.getByLabelText("完整 advanced_config JSON")).toHaveFocus();
    },
  );

  it("traps workspace focus and restores create focus after confirmed Escape", async () => {
    const confirm = vi
      .fn()
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);
    vi.stubGlobal("confirm", confirm);
    const user = await openCreate();
    const back = screen.getByRole("button", { name: "返回密钥列表" });
    await waitFor(() => expect(back).toHaveFocus());
    screen.getByRole("button", { name: "保存" }).focus();
    await user.tab();
    expect(back).toHaveFocus();
    await user.tab({ shift: true });
    expect(screen.getByRole("button", { name: "保存" })).toHaveFocus();

    await user.type(screen.getByLabelText("API Key"), "dirty");
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog", { name: "添加 API 密钥" })).toBeVisible();
    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "添加密钥" })).toHaveFocus(),
    );
  });

  it("traps focused JSON editing and restores its trigger on Escape", async () => {
    const user = await openCreate();
    const trigger = screen.getByRole("button", { name: "专注编辑 JSON" });
    await user.click(trigger);
    const textarea = screen.getByLabelText("专注 JSON 编辑器");
    await waitFor(() => expect(textarea).toHaveFocus());
    await user.tab();
    expect(screen.getByRole("button", { name: "格式化" })).toHaveFocus();
    await user.tab({ shift: true });
    expect(textarea).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("dialog", { name: "专注编辑 advanced_config" }),
    ).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("keeps only a manually edited URL when preset restore is cancelled", async () => {
    vi.stubGlobal(
      "confirm",
      vi.fn(() => false),
    );
    const user = await openCreate();
    await user.clear(screen.getByLabelText("Base URL"));
    await user.type(
      screen.getByLabelText("Base URL"),
      "https://manual.example/v1",
    );
    await user.selectOptions(screen.getByLabelText("服务商"), "claude");
    expect(window.confirm).toHaveBeenCalled();
    expect(screen.getByLabelText("Base URL")).toHaveValue(
      "https://manual.example/v1",
    );
    expect(screen.getByLabelText("默认兜底模型")).toHaveValue(
      "claude-haiku-4-5",
    );
    expect(screen.getByLabelText("官网地址")).toHaveValue(
      "https://www.anthropic.com/",
    );
    expect(screen.getByRole("button", { name: "关闭" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("keeps only manually edited thinking when preset restore is cancelled", async () => {
    vi.stubGlobal(
      "confirm",
      vi.fn(() => false),
    );
    const user = await openCreate();
    await user.click(screen.getByRole("button", { name: "请求配置" }));
    await user.click(screen.getByRole("button", { name: "自定义" }));
    fireEvent.change(screen.getByLabelText("请求体 JSON（自定义）"), {
      target: { value: '{"reasoning":{"effort":"high"}}' },
    });
    await user.selectOptions(screen.getByLabelText("服务商"), "claude");

    expect(window.confirm).toHaveBeenCalled();
    expect(screen.getByLabelText("Base URL")).toHaveValue(
      "https://api.anthropic.com/v1",
    );
    expect(screen.getByLabelText("默认兜底模型")).toHaveValue(
      "claude-haiku-4-5",
    );
    expect(screen.getByLabelText("官网地址")).toHaveValue(
      "https://www.anthropic.com/",
    );
    expect(screen.getByRole("button", { name: "自定义" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByLabelText("请求体 JSON（自定义）")).toHaveValue(
      '{"reasoning":{"effort":"high"}}',
    );
  });

  it("restores connection and thinking defaults when preset restore is confirmed", async () => {
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true),
    );
    const user = await openCreate();
    await user.clear(screen.getByLabelText("Base URL"));
    await user.type(
      screen.getByLabelText("Base URL"),
      "https://manual.example/v1",
    );
    await user.clear(screen.getByLabelText("默认兜底模型"));
    await user.type(screen.getByLabelText("默认兜底模型"), "manual-model");
    await user.clear(screen.getByLabelText("官网地址"));
    await user.type(
      screen.getByLabelText("官网地址"),
      "https://manual.example/",
    );
    await user.click(screen.getByRole("button", { name: "请求配置" }));
    await user.click(screen.getByRole("button", { name: "自定义" }));
    fireEvent.change(screen.getByLabelText("请求体 JSON（自定义）"), {
      target: { value: '{"reasoning":true}' },
    });
    await user.selectOptions(screen.getByLabelText("服务商"), "claude");

    expect(screen.getByLabelText("Base URL")).toHaveValue(
      "https://api.anthropic.com/v1",
    );
    expect(screen.getByLabelText("默认兜底模型")).toHaveValue(
      "claude-haiku-4-5",
    );
    expect(screen.getByLabelText("官网地址")).toHaveValue(
      "https://www.anthropic.com/",
    );
    expect(screen.getByRole("button", { name: "关闭" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(
      screen.queryByLabelText("请求体 JSON（自定义）"),
    ).not.toBeInTheDocument();
  });

  it("keeps every desktop section visible and uses navigation only for scrolling", async () => {
    mockViewport(false);
    const scrollIntoView = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollIntoView;
    const user = await openCreate();

    expect(screen.getByLabelText("API Key")).toBeVisible();
    expect(screen.getByLabelText("默认兜底模型")).toBeVisible();
    expect(screen.getByLabelText("完整 advanced_config JSON")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "模型映射" }));
    expect(scrollIntoView).toHaveBeenCalled();
    expect(screen.getByText("模型映射", { selector: "summary" })).toHaveFocus();
    expect(screen.getByLabelText("API Key")).toBeVisible();
  });

  it("uses collapsible accordion sections on mobile", async () => {
    mockViewport(true);
    const user = await openCreate();
    const identity = screen.getByText("基本信息", { selector: "summary" })
      .parentElement as HTMLDetailsElement;
    const connection = screen.getByText("连接设置", { selector: "summary" })
      .parentElement as HTMLDetailsElement;
    expect(identity.open).toBe(true);
    expect(connection.open).toBe(false);
    await user.click(screen.getByText("连接设置", { selector: "summary" }));
    expect(connection.open).toBe(true);
    expect(identity.open).toBe(false);
  });

  it("applies JSON only on command, preserves invalid raw text, and focus cancel discards edits", async () => {
    const user = await openCreate();
    await user.click(screen.getByRole("button", { name: "配置 JSON" }));
    const raw = screen.getByLabelText("完整 advanced_config JSON");
    fireEvent.change(raw, {
      target: {
        value:
          '{"version":1,"fallback_model":"from-json","vendor":{"keep":true}}',
      },
    });
    expect(screen.getByLabelText("默认兜底模型")).not.toHaveValue("from-json");
    await user.click(screen.getByRole("button", { name: "应用 JSON" }));
    expect(screen.getByLabelText("默认兜底模型")).toHaveValue("from-json");
    await user.click(screen.getByRole("button", { name: "专注编辑 JSON" }));
    await user.type(screen.getByLabelText("专注 JSON 编辑器"), " broken");
    await user.click(screen.getByRole("button", { name: "取消专注编辑" }));
    expect(screen.getByLabelText("完整 advanced_config JSON")).not.toHaveValue(
      expect.stringContaining("broken"),
    );
    fireEvent.change(raw, { target: { value: "{bad" } });
    await user.click(screen.getByRole("button", { name: "应用 JSON" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/line 1, column/i);
    expect(screen.getByLabelText("默认兜底模型")).toHaveValue("from-json");
  });

  it("saves an applied JSON fallback as both canonical model fields", async () => {
    const user = await openCreate();
    await user.type(screen.getByLabelText("API Key"), "draft-secret");
    await user.click(screen.getByRole("button", { name: "配置 JSON" }));
    fireEvent.change(screen.getByLabelText("完整 advanced_config JSON"), {
      target: {
        value: '{"version":1,"fallback_model":"json-canonical"}',
      },
    });
    await user.click(screen.getByRole("button", { name: "应用 JSON" }));
    expect(screen.getByLabelText("默认兜底模型")).toHaveValue("json-canonical");
    await user.click(screen.getByRole("button", { name: "保存配置" }));

    expect(apiAccountApi.create).toHaveBeenCalledWith(
      expect.objectContaining({
        model: "json-canonical",
        advanced_config: expect.objectContaining({
          fallback_model: "json-canonical",
        }),
      }),
    );
  });

  it("validates the current unsaved draft without clearing dirty state", async () => {
    vi.mocked(apiAccountApi.validateDraft).mockResolvedValue({
      status: "success",
      message: "连接成功",
      http_status: 200,
      section: "connection",
      latency_ms: 35,
    });
    const user = await openCreate();
    await user.type(screen.getByLabelText("API Key"), "draft-secret");
    await user.click(screen.getByRole("button", { name: "测试连接" }));
    await waitFor(() =>
      expect(apiAccountApi.validateDraft).toHaveBeenCalledWith(
        expect.objectContaining({
          api_key: "draft-secret",
          provider: "deepseek",
        }),
      ),
    );
    expect(screen.getByText(/200.*35 ms.*连接成功/)).toBeVisible();
    expect(screen.getByText("未保存")).toBeVisible();
  });

  it.each([
    ["authentication_failed", "authentication", "api-account-api-key"],
    ["endpoint_unreachable", "endpoint", "api-account-base-url"],
    ["model_unavailable", "model", "api-account-model"],
    ["invalid_configuration", "basic", "api-account-provider"],
    ["invalid_configuration", "configuration", "api-account-headers"],
    ["invalid_configuration", "json", "api-account-advanced-json"],
  ] as const)(
    "locates %s validation failures from the %s section without exposing the key",
    async (status, section, targetId) => {
      mockViewport(true);
      vi.mocked(apiAccountApi.validateDraft).mockResolvedValue({
        status,
        message: "failure contained draft-secret",
        http_status: 400,
        section,
        latency_ms: 12,
      });
      const user = await openCreate();
      await user.type(screen.getByLabelText("API Key"), "draft-secret");
      await user.click(screen.getByRole("button", { name: "测试连接" }));

      await waitFor(() =>
        expect(document.getElementById(targetId)).toHaveFocus(),
      );
      expect(screen.queryByText(/failure contained draft-secret/)).toBeNull();
      expect(screen.getByText(/failure contained \[redacted\]/)).toBeVisible();
      expect(
        document.getElementById(targetId)?.closest("details"),
      ).toHaveAttribute("open");
    },
  );

  it("does local validation before requests and reduces Tavily to service configuration", async () => {
    const user = await openCreate();
    await user.click(screen.getByRole("button", { name: "测试连接" }));
    expect(apiAccountApi.validateDraft).not.toHaveBeenCalled();
    expect(screen.getByLabelText("API Key")).toHaveFocus();
    await user.selectOptions(screen.getByLabelText("服务商"), "tavily");
    expect(
      screen.queryByRole("button", { name: "模型映射" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "请求配置" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "配置 JSON" }),
    ).not.toBeInTheDocument();
  });

  it("keeps invalid mapping, header, and body drafts local", async () => {
    const user = await openCreate();
    await user.type(screen.getByLabelText("API Key"), "draft-secret");
    await user.click(screen.getByRole("button", { name: "模型映射" }));
    await user.click(screen.getByRole("button", { name: "添加模型映射" }));
    await user.click(screen.getByRole("button", { name: "测试连接" }));
    expect(apiAccountApi.validateDraft).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/模型映射/);
    await user.type(screen.getByLabelText("模型别名 1"), "chat");
    await user.type(screen.getByLabelText("真实模型 ID 1"), "real-chat");
    await user.click(screen.getByRole("button", { name: "请求配置" }));
    await user.click(screen.getByRole("button", { name: "添加 Header" }));
    await user.type(screen.getByLabelText("Header 名称 1"), "Authorization");
    await user.type(screen.getByLabelText("Header 值 1"), "secret");
    await user.click(screen.getByRole("button", { name: "测试连接" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      /headers\.Authorization/,
    );
    expect(apiAccountApi.validateDraft).not.toHaveBeenCalled();
  });

  it.each([
    ["Base URL", "not-a-url", "测试连接"],
    ["Base URL", "ftp://api.example.com", "保存配置"],
    ["官网地址", "https:///", "测试连接"],
  ])("rejects invalid %s value %s before %s", async (label, value, action) => {
    const user = await openCreate();
    await user.type(screen.getByLabelText("API Key"), "draft-secret");
    await user.clear(screen.getByLabelText(label));
    await user.type(screen.getByLabelText(label), value);
    await user.click(screen.getByRole("button", { name: action }));

    expect(apiAccountApi.validateDraft).not.toHaveBeenCalled();
    expect(apiAccountApi.create).not.toHaveBeenCalled();
    expect(screen.getByLabelText(label)).toHaveFocus();
  });
});
