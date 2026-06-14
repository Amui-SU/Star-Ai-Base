import { describe, expect, it } from "vitest";
import {
  formatThinkingConfig,
  inferThinkingMode,
  parseThinkingConfig,
} from "./thinkingConfig";

describe("thinkingConfig", () => {
  const template = {
    thinking: { type: "enabled" },
    reasoning_effort: "high",
  };

  it("infers off, standard, and custom modes", () => {
    expect(inferThinkingMode({}, template)).toBe("off");
    expect(inferThinkingMode(template, template)).toBe("standard");
    expect(inferThinkingMode({ thinking: { type: "enabled" } }, template)).toBe(
      "custom",
    );
  });

  it("formats and parses editable JSON objects", () => {
    const formatted = formatThinkingConfig(template);
    expect(formatted).toContain('"thinking"');
    expect(parseThinkingConfig(formatted)).toEqual(template);
  });

  it("rejects arrays and invalid JSON", () => {
    expect(() => parseThinkingConfig("[]")).toThrow("JSON 对象");
    expect(() => parseThinkingConfig("{bad")).toThrow("JSON 格式");
  });
});
