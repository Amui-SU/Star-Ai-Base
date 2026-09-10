import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AuthPage from "@/components/AuthPage";

const apiMocks = vi.hoisted(() => ({
  sendPasswordResetCode: vi.fn(),
  confirmPasswordReset: vi.fn(),
}));

vi.mock("@/components/LocalConnectionSettings", () => ({
  default: () => null,
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    systemAuthApi: {
      ...actual.systemAuthApi,
      getOAuthLoginUrl: vi.fn((provider: string) => `/oauth/${provider}`),
      sendPasswordResetCode: apiMocks.sendPasswordResetCode,
      confirmPasswordReset: apiMocks.confirmPasswordReset,
    },
  };
});

async function openPasswordReset(user: ReturnType<typeof userEvent.setup>) {
  render(<AuthPage onAuthSuccess={vi.fn()} />);
  await user.type(
    screen.getByPlaceholderText("输入邮箱地址"),
    "member@example.com",
  );
  await user.click(screen.getByRole("button", { name: "继续" }));
  await user.click(screen.getByRole("button", { name: "忘记密码？" }));
}

async function fillResetForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText("验证码"), "123456");
  await user.type(screen.getByPlaceholderText("设置新密码"), "new password");
  await user.type(screen.getByPlaceholderText("确认新密码"), "new password");
}

beforeEach(() => {
  vi.stubGlobal("location", {
    ...window.location,
    protocol: "http:",
    hostname: "mobile-preview.example.test",
    origin: "http://mobile-preview.example.test",
  });
  apiMocks.sendPasswordResetCode.mockResolvedValue({
    message: "code sent",
    code: "123456",
  });
  apiMocks.confirmPasswordReset.mockResolvedValue({
    message: "密码已重置，请使用新密码登录",
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("AuthPage password reset", () => {
  it("opens the reset step and sends a dedicated reset code", async () => {
    const user = userEvent.setup();
    await openPasswordReset(user);

    expect(
      screen.getByRole("heading", { name: "重置密码" }),
    ).toBeInTheDocument();
    expect(screen.getByText("member@example.com")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "获取验证码" }));

    expect(apiMocks.sendPasswordResetCode).toHaveBeenCalledWith(
      "member@example.com",
    );
    expect(screen.getByText("验证码: 123456")).toBeInTheDocument();
  });

  it("rejects mismatched passwords without submitting", async () => {
    const user = userEvent.setup();
    await openPasswordReset(user);
    await user.type(screen.getByPlaceholderText("验证码"), "123456");
    await user.type(screen.getByPlaceholderText("设置新密码"), "new password");
    await user.type(
      screen.getByPlaceholderText("确认新密码"),
      "different password",
    );

    await user.click(screen.getByRole("button", { name: "确认重置" }));

    expect(screen.getByText("两次输入的密码不一致")).toBeInTheDocument();
    expect(apiMocks.confirmPasswordReset).not.toHaveBeenCalled();
  });

  it("requires a verification code before submitting", async () => {
    const user = userEvent.setup();
    await openPasswordReset(user);
    await user.type(screen.getByPlaceholderText("设置新密码"), "new password");
    await user.type(screen.getByPlaceholderText("确认新密码"), "new password");

    await user.click(screen.getByRole("button", { name: "确认重置" }));

    expect(screen.getByText("请输入验证码")).toBeInTheDocument();
    expect(apiMocks.confirmPasswordReset).not.toHaveBeenCalled();
  });

  it("returns to login with cleared secrets and a success notice", async () => {
    const user = userEvent.setup();
    await openPasswordReset(user);
    await fillResetForm(user);

    await user.click(screen.getByRole("button", { name: "确认重置" }));

    expect(apiMocks.confirmPasswordReset).toHaveBeenCalledWith({
      email: "member@example.com",
      code: "123456",
      new_password: "new password",
    });
    expect(
      await screen.findByRole("heading", { name: "输入密码" }),
    ).toBeInTheDocument();
    expect(screen.getByText("密码已重置，请使用新密码登录")).toHaveAttribute(
      "role",
      "status",
    );
    expect(screen.getByPlaceholderText("输入密码")).toHaveValue("");
  });

  it("shows API errors and allows retry", async () => {
    apiMocks.sendPasswordResetCode
      .mockRejectedValueOnce(new Error("发送失败，请稍后重试"))
      .mockResolvedValueOnce({ message: "code sent", code: "123456" });
    const user = userEvent.setup();
    await openPasswordReset(user);

    await user.click(screen.getByRole("button", { name: "获取验证码" }));
    expect(screen.getByText("发送失败，请稍后重试")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "获取验证码" }));
    expect(apiMocks.sendPasswordResetCode).toHaveBeenCalledTimes(2);
  });

  it("returns to login without changing the selected email", async () => {
    const user = userEvent.setup();
    await openPasswordReset(user);

    await user.click(screen.getByRole("button", { name: "返回登录" }));

    expect(
      screen.getByRole("heading", { name: "输入密码" }),
    ).toBeInTheDocument();
    expect(screen.getByText("member@example.com")).toBeInTheDocument();
  });
});
