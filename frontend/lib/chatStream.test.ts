import { describe, expect, it } from "vitest";
import { parseChatStream } from "./chatStream";

describe("parseChatStream", () => {
  it("separates interleaved thinking deltas from answer text", () => {
    const result = parseChatStream(
      '[[THINKING_DELTA]]"先分析"\n回答[[THINKING_DELTA]]"再判断"\n完成',
    );

    expect(result.answer).toBe("回答完成");
    expect(result.thinking).toBe("先分析再判断");
    expect(result.sources).toEqual([]);
  });

  it("does not leak a partial thinking marker into the answer", () => {
    const result = parseChatStream('回答[[THINKING_DELTA]]"未完成');

    expect(result.answer).toBe("回答");
    expect(result.thinking).toBe("");
  });

  it("prefers final thinking json and parses sources", () => {
    const result = parseChatStream(
      '回答\n[[THINKING_JSON]]"完整思考"\n[[SOURCES_JSON]][{"bvid":"BV1","title":"来源","url":"https://example.com"}]',
    );

    expect(result.answer).toBe("回答");
    expect(result.thinking).toBe("完整思考");
    expect(result.sources).toHaveLength(1);
    expect(result.complete).toBe(true);
  });
});
