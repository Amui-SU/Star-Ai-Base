import { cleanup, render, screen } from "@testing-library/react";
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
      validateDraft: vi.fn(),
      remove: vi.fn(),
    },
    chatApi: { ...actual.chatApi, getModelConfig: vi.fn() },
  };
});

export const account: ApiAccount = {
  id: 7,
  provider: "deepseek",
  provider_label: "DeepSeek",
  display_name: "Work DeepSeek",
  base_url: "https://api.deepseek.com/v1",
  model: "deepseek-chat",
  protocol: "openai_compatible",
  auth_scheme: "bearer",
  website_url: "https://deepseek.com",
  notes: "production",
  advanced_config: {
    version: 1,
    model_mapping: { chat: "deepseek-chat" },
    fallback_model: "deepseek-chat",
    user_agent: "",
    headers: {},
    body: {},
    vendor: { keep: true },
  },
  thinking_config: { reasoning: { enabled: true } },
  enabled: true,
  is_default: true,
  configured: true,
  last_validated_at: null,
  last_error: null,
};

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

describe("ApiAccountsPanel", () => {
  it("keeps the list in its modal and opens create as a full-screen dialog", async () => {
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={vi.fn()} />);
    await screen.findByText("还没有 AI 服务密钥");
    expect(
      document.querySelector(".modal-card.api-accounts-panel"),
    ).not.toBeNull();
    await user.click(screen.getByRole("button", { name: "添加密钥" }));
    expect(screen.getByRole("dialog", { name: "添加 API 密钥" })).toHaveClass(
      "api-account-workspace",
    );
    expect(
      document.querySelector(".api-account-workspace .modal-card"),
    ).toBeNull();
  });

  it("locks provider while editing and omits a blank API key from the complete payload", async () => {
    vi.mocked(apiAccountApi.list).mockResolvedValue([account]);
    vi.mocked(apiAccountApi.update).mockResolvedValue(account);
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: /^Work DeepSeek/ }),
    );
    expect(screen.getByLabelText("服务商")).toBeDisabled();
    await user.clear(screen.getByLabelText("备注"));
    await user.type(screen.getByLabelText("备注"), "updated");
    await user.clear(screen.getByLabelText("默认模型"));
    await user.type(screen.getByLabelText("默认模型"), "deepseek-v3-updated");
    await user.click(screen.getByRole("button", { name: "保存配置" }));
    expect(apiAccountApi.update).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        notes: "updated",
        protocol: "openai_compatible",
        auth_scheme: "bearer",
        website_url: "https://deepseek.com",
        model: "deepseek-v3-updated",
        advanced_config: expect.objectContaining({
          fallback_model: "deepseek-v3-updated",
          model_mapping: { chat: "deepseek-chat" },
          vendor: { keep: true },
        }),
        thinking_config: { reasoning: { enabled: true } },
      }),
    );
    expect(apiAccountApi.update).toHaveBeenCalledWith(
      7,
      expect.not.objectContaining({ api_key: expect.anything() }),
    );
  });

  it("confirms dirty navigation, registers beforeunload, and does not close the manager", async () => {
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={onClose} />);
    await screen.findByText("还没有 AI 服务密钥");
    await user.click(screen.getByRole("button", { name: "添加密钥" }));
    await user.type(screen.getByLabelText("API Key"), "secret");
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    await user.click(screen.getByRole("button", { name: "返回密钥列表" }));
    expect(confirm).toHaveBeenCalledWith("当前配置尚未保存，确认离开？");
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "添加 API 密钥" })).toBeVisible();
  });

  it("locks navigation and duplicate submission while saving", async () => {
    let resolveCreate: ((value: ApiAccount) => void) | undefined;
    vi.mocked(apiAccountApi.create).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve;
        }),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ApiAccountsPanel open onClose={onClose} />);
    await screen.findByText("还没有 AI 服务密钥");
    await user.click(screen.getByRole("button", { name: "添加密钥" }));
    await user.type(screen.getByLabelText("API Key"), "secret");
    await user.click(screen.getByRole("button", { name: "保存配置" }));
    expect(screen.getByRole("button", { name: "返回密钥列表" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "关闭密钥管理" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "保存中..." })).toBeDisabled();
    expect(apiAccountApi.create).toHaveBeenCalledOnce();
    expect(onClose).not.toHaveBeenCalled();
    resolveCreate?.(account);
  });
});
