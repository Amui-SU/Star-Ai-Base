import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ApiAccountsPanel from "@/components/ApiAccountsPanel";
import { apiAccountApi, type ApiAccount } from "@/lib/api";

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
  };
});

const deepseekAccount: ApiAccount = {
  id: 7,
  provider: "deepseek",
  provider_label: "DeepSeek",
  display_name: "My DeepSeek",
  base_url: "https://api.deepseek.com/v1",
  model: "deepseek-chat",
  thinking_config: {},
  enabled: true,
  is_default: true,
  configured: true,
  last_validated_at: null,
  last_error: null,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("ApiAccountsPanel", () => {
  it("loads an empty account list and creates a new account", async () => {
    vi.mocked(apiAccountApi.list).mockResolvedValue([]);
    vi.mocked(apiAccountApi.create).mockResolvedValue(deepseekAccount);
    const onChanged = vi.fn();
    const user = userEvent.setup();

    render(<ApiAccountsPanel open onClose={vi.fn()} onChanged={onChanged} />);

    expect(await screen.findByText("还没有 AI 服务密钥")).toBeVisible();
    await user.type(screen.getByLabelText("API Key"), "sk-user-secret");
    await user.click(screen.getByRole("button", { name: "添加密钥" }));

    await waitFor(() =>
      expect(apiAccountApi.create).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "deepseek",
          api_key: "sk-user-secret",
          model: "deepseek-chat",
        }),
      ),
    );
    expect(onChanged).toHaveBeenCalled();
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
      await screen.findByRole("button", { name: /My DeepSeek/ }),
    );
    await user.clear(screen.getByLabelText("密钥名称"));
    await user.type(screen.getByLabelText("密钥名称"), "Updated DeepSeek");
    await user.click(screen.getByRole("button", { name: "保存修改" }));

    await waitFor(() =>
      expect(apiAccountApi.update).toHaveBeenCalledWith(
        7,
        expect.not.objectContaining({ api_key: expect.anything() }),
      ),
    );
    expect(apiAccountApi.update).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ display_name: "Updated DeepSeek" }),
    );
  });

  it("confirms before deleting an account", async () => {
    vi.mocked(apiAccountApi.list).mockResolvedValue([deepseekAccount]);
    vi.mocked(apiAccountApi.remove).mockResolvedValue(undefined);
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true),
    );
    const user = userEvent.setup();

    render(<ApiAccountsPanel open onClose={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "删除" }));

    await waitFor(() => expect(apiAccountApi.remove).toHaveBeenCalledWith(7));
    expect(window.confirm).toHaveBeenCalledWith("删除 My DeepSeek？");
  });
});
