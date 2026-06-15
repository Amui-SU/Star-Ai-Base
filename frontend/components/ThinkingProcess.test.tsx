import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ThinkingProcess from "./ThinkingProcess";

describe("ThinkingProcess", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows live thinking content in an expanded state", () => {
    vi.useFakeTimers();
    vi.setSystemTime(7_000);

    render(
      <ThinkingProcess active startedAt={1_000} thinking="正在分析资料" />,
    );

    expect(screen.getByText(/正在思考 · 6\.0 秒/)).toBeInTheDocument();
    expect(screen.getByText("正在分析资料")).toBeVisible();

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(screen.getByText(/正在思考 · 6\.5 秒/)).toBeInTheDocument();
  });

  it("shows a useful status while waiting for the first thinking delta", () => {
    render(<ThinkingProcess active startedAt={Date.now()} thinking="" />);

    expect(
      screen.getByText("正在读取知识库并等待模型返回思考内容"),
    ).toBeVisible();
  });

  it("starts collapsed after completion and can be expanded", () => {
    render(
      <ThinkingProcess
        active={false}
        startedAt={1_000}
        durationMs={9_400}
        thinking="完整思考内容"
      />,
    );

    expect(screen.getByText("已思考 9.4 秒")).toBeInTheDocument();
    expect(screen.queryByText("完整思考内容")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /已思考 9\.4 秒/ }));
    expect(screen.getByText("完整思考内容")).toBeVisible();
  });

  it("explains when a completed request has no thinking content", () => {
    render(
      <ThinkingProcess
        active={false}
        startedAt={1_000}
        durationMs={3_000}
        thinking=""
      />,
    );

    expect(screen.getByText("已完成生成 · 未返回独立思考内容")).toBeVisible();
  });
});
