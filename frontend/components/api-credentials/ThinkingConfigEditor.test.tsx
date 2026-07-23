import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { formatThinkingConfig } from "@/lib/thinkingConfig";
import { ThinkingConfigEditor } from "./ThinkingConfigEditor";

afterEach(cleanup);

const template = {
  thinking: { type: "enabled" },
  reasoning_effort: "high",
};

function renderEditor(
  overrides: Partial<React.ComponentProps<typeof ThinkingConfigEditor>> = {},
) {
  const props: React.ComponentProps<typeof ThinkingConfigEditor> = {
    mode: "standard",
    customJson: '{"thinking":{"type":"enabled"}}',
    template,
    error: "",
    onModeChange: vi.fn(),
    onCustomJsonChange: vi.fn(),
    onErrorChange: vi.fn(),
    ...overrides,
  };

  render(<ThinkingConfigEditor {...props} />);
  return props;
}

describe("ThinkingConfigEditor", () => {
  it("shows the formatted standard template in a read-only textarea", () => {
    renderEditor();

    const textarea = screen.getByRole("textbox", {
      name: "请求体 JSON（标准模板）",
    });
    expect(textarea).toHaveValue(formatThinkingConfig(template));
    expect(textarea).toHaveAttribute("readonly");
  });

  it("disables standard mode for an empty template and hides JSON when off", () => {
    const { rerender } = render(
      <ThinkingConfigEditor
        mode="off"
        customJson="{}"
        template={{}}
        error=""
        onModeChange={vi.fn()}
        onCustomJsonChange={vi.fn()}
        onErrorChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "标准" })).toBeDisabled();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();

    rerender(
      <ThinkingConfigEditor
        mode="standard"
        customJson="{}"
        template={{}}
        error=""
        onModeChange={vi.fn()}
        onCustomJsonChange={vi.fn()}
        onErrorChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "标准" })).toBeDisabled();
  });

  it("shows and edits the custom JSON draft", async () => {
    const user = userEvent.setup();
    const props = renderEditor({ mode: "custom", customJson: '{"foo":1}' });
    const textarea = screen.getByRole("textbox", {
      name: "请求体 JSON（自定义）",
    });

    expect(textarea).toHaveValue('{"foo":1}');
    await user.type(textarea, " ");

    expect(props.onCustomJsonChange).toHaveBeenCalledWith('{"foo":1} ');
  });

  it("formats a valid custom JSON object and clears its error", async () => {
    const user = userEvent.setup();
    const props = renderEditor({ mode: "custom", customJson: '{"foo":1}' });

    await user.click(screen.getByRole("button", { name: "格式化 JSON" }));

    expect(props.onCustomJsonChange).toHaveBeenCalledWith(
      formatThinkingConfig({ foo: 1 }),
    );
    expect(props.onErrorChange).toHaveBeenCalledWith("");
  });

  it("reports invalid JSON without changing the draft", async () => {
    const user = userEvent.setup();
    const props = renderEditor({ mode: "custom", customJson: "{bad" });

    await user.click(screen.getByRole("button", { name: "格式化 JSON" }));

    expect(props.onErrorChange).toHaveBeenCalledWith("思考配置 JSON 格式错误");
    expect(props.onCustomJsonChange).not.toHaveBeenCalled();
  });

  it("changes mode without overwriting custom JSON", async () => {
    const user = userEvent.setup();
    const props = renderEditor({
      mode: "custom",
      customJson: '{"saved":true}',
    });

    await user.click(screen.getByRole("button", { name: "关闭" }));
    await user.click(screen.getByRole("button", { name: "标准" }));

    expect(props.onModeChange).toHaveBeenNthCalledWith(1, "off");
    expect(props.onModeChange).toHaveBeenNthCalledWith(2, "standard");
    expect(props.onCustomJsonChange).not.toHaveBeenCalled();
  });
});
