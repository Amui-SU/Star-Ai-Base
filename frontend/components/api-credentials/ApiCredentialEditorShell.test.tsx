import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiCredentialEditorShell } from "./ApiCredentialEditorShell";

afterEach(cleanup);

function renderShell(
  overrides: Partial<
    React.ComponentProps<typeof ApiCredentialEditorShell>
  > = {},
) {
  const props: React.ComponentProps<typeof ApiCredentialEditorShell> = {
    title: "编辑 API 密钥",
    subtitle: "配置模型服务凭据",
    activeTab: "basic",
    showRequestTab: true,
    saving: false,
    onClose: vi.fn(),
    onTabChange: vi.fn(),
    basicContent: <div>基础内容</div>,
    requestContent: <div>请求内容</div>,
    footer: <div>编辑器操作</div>,
    ...overrides,
  };

  render(<ApiCredentialEditorShell {...props} />);
  return props;
}

describe("ApiCredentialEditorShell", () => {
  it("renders its heading, tabs, active content, and footer", () => {
    renderShell();

    expect(
      screen.getByRole("heading", { name: "编辑 API 密钥" }),
    ).toBeInTheDocument();
    expect(screen.getByText("配置模型服务凭据")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "基础配置" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "请求配置" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
    expect(screen.getByText("基础内容")).toBeInTheDocument();
    expect(screen.getByText("编辑器操作")).toBeInTheDocument();
  });

  it("reports request tab selection", async () => {
    const user = userEvent.setup();
    const props = renderShell();

    await user.click(screen.getByRole("tab", { name: "请求配置" }));

    expect(props.onTabChange).toHaveBeenCalledWith("request");
  });

  it("links stable tab controls to the active request panel", () => {
    renderShell({ activeTab: "request" });

    const basicTab = screen.getByRole("tab", { name: "基础配置" });
    const requestTab = screen.getByRole("tab", { name: "请求配置" });
    const activePanel = screen.getByRole("tabpanel");

    expect(basicTab).toHaveAttribute("aria-selected", "false");
    expect(basicTab).toHaveAttribute(
      "aria-controls",
      "api-credential-basic-panel",
    );
    expect(requestTab).toHaveAttribute("aria-selected", "true");
    expect(requestTab).toHaveAttribute(
      "aria-controls",
      "api-credential-request-panel",
    );
    expect(activePanel).toHaveAttribute("id", "api-credential-request-panel");
    expect(activePanel).toHaveAttribute(
      "aria-labelledby",
      "api-credential-request-tab",
    );
    expect(screen.getByText("请求内容")).toBeInTheDocument();
    expect(screen.queryByText("基础内容")).not.toBeInTheDocument();
  });

  it("omits the back action when no handler is provided", () => {
    renderShell();

    expect(
      screen.queryByRole("button", { name: "返回密钥列表" }),
    ).not.toBeInTheDocument();
  });

  it("supports an optional back action and hides the request tab", async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();
    renderShell({ onBack, showRequestTab: false });

    const backButton = screen.getByRole("button", { name: "返回密钥列表" });
    expect(backButton).toHaveTextContent("返回密钥列表");
    await user.click(backButton);

    expect(onBack).toHaveBeenCalledOnce();
    expect(
      screen.queryByRole("tab", { name: "请求配置" }),
    ).not.toBeInTheDocument();
  });

  it("disables navigation actions while saving but keeps the footer", () => {
    renderShell({ saving: true, onBack: vi.fn() });

    expect(screen.getByRole("button", { name: "返回密钥列表" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "关闭" })).toBeDisabled();
    expect(screen.getByText("编辑器操作")).toBeInTheDocument();
  });
});
