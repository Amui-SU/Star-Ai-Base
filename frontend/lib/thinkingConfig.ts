export type ThinkingMode = "off" | "standard" | "custom";
export type ThinkingConfig = Record<string, unknown>;

function sortJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortJson);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nested]) => [key, sortJson(nested)]),
    );
  }
  return value;
}

function stableJson(value: ThinkingConfig): string {
  return JSON.stringify(sortJson(value));
}

export function inferThinkingMode(
  config: ThinkingConfig,
  template: ThinkingConfig,
): ThinkingMode {
  if (Object.keys(config).length === 0) return "off";
  return stableJson(config) === stableJson(template) ? "standard" : "custom";
}

export function formatThinkingConfig(config: ThinkingConfig): string {
  return JSON.stringify(config, null, 2);
}

export function parseThinkingConfig(raw: string): ThinkingConfig {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("思考配置 JSON 格式错误");
  }
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("思考配置必须是 JSON 对象");
  }
  return parsed as ThinkingConfig;
}
