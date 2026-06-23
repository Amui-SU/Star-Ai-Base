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

  it("separates web search progress from answer and thinking text", () => {
    const result = parseChatStream(
      '[[WEB_SEARCH_PROGRESS]]"正在联网搜索外部资料"\n[[THINKING_DELTA]]"模型思考"\n回答',
    );

    expect(result.answer).toBe("回答");
    expect(result.thinking).toBe("模型思考");
    expect(result.webSearchProgress).toBe("正在联网搜索外部资料");
  });

  it("uses an empty web search progress marker to clear the active state", () => {
    const result = parseChatStream(
      '[[WEB_SEARCH_PROGRESS]]"正在联网搜索外部资料"\n回答\n[[WEB_SEARCH_PROGRESS]]""\n[[SOURCES_JSON]][]',
    );

    expect(result.answer).toBe("回答");
    expect(result.webSearchProgress).toBe("");
    expect(result.complete).toBe(true);
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

  it("parses web search metadata without leaking it into the answer", () => {
    const result = parseChatStream(
      '回答\n[[WEB_SEARCH_JSON]]{"status":"failed","message":"联网搜索失败，已仅参考知识库","result_count":0,"queries":["query"],"results":[{"title":"Web Result","url":"https://example.com","snippet":"Snippet"}]}\n[[SOURCES_JSON]][]',
    );

    expect(result.answer).toBe("回答");
    expect(result.webSearch).toEqual({
      status: "failed",
      message: "联网搜索失败，已仅参考知识库",
      result_count: 0,
      queries: ["query"],
      results: [
        {
          title: "Web Result",
          url: "https://example.com",
          snippet: "Snippet",
        },
      ],
    });
    expect(result.complete).toBe(true);
  });

  it("treats metadata-looking text inside an answer as normal answer text", () => {
    const result = parseChatStream(
      "回答里提到 [[SOURCES_JSON]] 这个标记\n[[SOURCES_JSON]][]",
    );

    expect(result.answer).toBe("回答里提到 [[SOURCES_JSON]] 这个标记");
    expect(result.complete).toBe(true);
  });

  it("uses the final metadata marker when an answer contains marker text on its own line", () => {
    const result = parseChatStream(
      "示例：\n[[SOURCES_JSON]]\n不是元数据\n[[SOURCES_JSON]][]",
    );

    expect(result.answer).toBe("示例：\n[[SOURCES_JSON]]\n不是元数据");
    expect(result.sources).toEqual([]);
    expect(result.complete).toBe(true);
  });

  it("does not mark the stream complete when sources metadata is incomplete", () => {
    const result = parseChatStream("回答\n[[SOURCES_JSON]]");

    expect(result.answer).toBe("回答\n[[SOURCES_JSON]]");
    expect(result.sources).toEqual([]);
    expect(result.complete).toBe(false);
  });
});
