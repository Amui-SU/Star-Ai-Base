import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  RefreshBusProvider,
  useRefreshEmit,
  useRefreshVersion,
  type RefreshTopic,
} from "@/hooks/refreshBus";

function Probe({ topic }: { topic: RefreshTopic }) {
  const version = useRefreshVersion(topic);
  return <span data-testid={`version-${topic}`}>{version}</span>;
}

function EmitButton({ topic }: { topic: RefreshTopic }) {
  const emit = useRefreshEmit();
  return (
    <button type="button" onClick={() => emit(topic)}>
      emit-{topic}
    </button>
  );
}

describe("refreshBus", () => {
  it("只递增同主题订阅者的版本号", async () => {
    const user = userEvent.setup();
    render(
      <RefreshBusProvider>
        <Probe topic="kb-stats" />
        <Probe topic="chat-history" />
        <EmitButton topic="kb-stats" />
      </RefreshBusProvider>,
    );

    expect(screen.getByTestId("version-kb-stats")).toHaveTextContent("0");

    await user.click(screen.getByRole("button", { name: "emit-kb-stats" }));
    await user.click(screen.getByRole("button", { name: "emit-kb-stats" }));

    expect(screen.getByTestId("version-kb-stats")).toHaveTextContent("2");
    expect(screen.getByTestId("version-chat-history")).toHaveTextContent("0");
  });

  it("同主题多个订阅者同时收到通知", async () => {
    const user = userEvent.setup();
    render(
      <RefreshBusProvider>
        <div data-testid="first">
          <Probe topic="api-accounts" />
        </div>
        <div data-testid="second">
          <Probe topic="api-accounts" />
        </div>
        <EmitButton topic="api-accounts" />
      </RefreshBusProvider>,
    );

    await user.click(screen.getByRole("button", { name: "emit-api-accounts" }));

    expect(screen.getByTestId("first")).toHaveTextContent("1");
    expect(screen.getByTestId("second")).toHaveTextContent("1");
  });

  it("无 Provider 时版本号保持 0 且 emit 不报错", async () => {
    const user = userEvent.setup();
    render(
      <>
        <Probe topic="knowledge-bases" />
        <EmitButton topic="knowledge-bases" />
      </>,
    );

    await user.click(
      screen.getByRole("button", { name: "emit-knowledge-bases" }),
    );

    expect(screen.getByTestId("version-knowledge-bases")).toHaveTextContent(
      "0",
    );
  });
});
