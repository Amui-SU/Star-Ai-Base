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

async function openCreate() {
  const user = userEvent.setup();
  render(<ApiAccountsPanel open onClose={vi.fn()} />);
  await screen.findByText("还没有 AI 服务密钥");
  await user.click(screen.getByRole("button", { name: "添加密钥" }));
  return user;
}

describe("ApiAccountWorkspace", () => {
  it("protects manually edited connection values on preset switch", async () => {
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
    expect(screen.getByLabelText("兜底模型")).not.toHaveValue("from-json");
    await user.click(screen.getByRole("button", { name: "应用 JSON" }));
    expect(screen.getByLabelText("兜底模型")).toHaveValue("from-json");
    await user.click(screen.getByRole("button", { name: "专注编辑 JSON" }));
    await user.type(screen.getByLabelText("专注 JSON 编辑器"), " broken");
    await user.click(screen.getByRole("button", { name: "取消专注编辑" }));
    expect(screen.getByLabelText("完整 advanced_config JSON")).not.toHaveValue(
      expect.stringContaining("broken"),
    );
    fireEvent.change(raw, { target: { value: "{bad" } });
    await user.click(screen.getByRole("button", { name: "应用 JSON" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/line 1, column/i);
    expect(screen.getByLabelText("兜底模型")).toHaveValue("from-json");
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
});
