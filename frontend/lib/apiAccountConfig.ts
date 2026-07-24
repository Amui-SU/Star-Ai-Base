export interface ApiAccountAdvancedConfig {
  version: 1;
  model_mapping: Record<string, string>;
  fallback_model: string;
  user_agent: string;
  headers: Record<string, string>;
  body: Record<string, unknown>;
  [key: string]: unknown;
}

export class ApiAccountConfigError extends Error {
  constructor(
    message: string,
    readonly path: string,
    readonly line?: number,
    readonly column?: number,
  ) {
    super(message);
    this.name = "ApiAccountConfigError";
  }
}

const protectedHeaders = new Set([
  "authorization",
  "baggage",
  "cdn-loop",
  "connection",
  "content-length",
  "forwarded",
  "host",
  "proxy-authorization",
  "traceparent",
  "tracestate",
  "transfer-encoding",
  "user-agent",
  "via",
  "x-amzn-trace-id",
  "x-client-ip",
  "x-cloud-trace-context",
  "x-correlation-id",
  "x-real-ip",
  "x-request-id",
  "x-trace-id",
]);
const protectedHeaderPrefixes = [
  "cf-connecting-",
  "x-b3-",
  "x-datadog-",
  "x-envoy-",
  "x-forwarded-",
  "x-original-",
  "x-proxy-",
];
const protectedBody = new Set([
  "apikey",
  "authorization",
  "baseurl",
  "input",
  "messages",
  "model",
  "prompt",
  "requestid",
  "responseformat",
  "stream",
  "toolchoice",
  "tools",
  "traceid",
  "url",
]);
const headerToken = /^[!#$%&'*+.^_`|~A-Za-z0-9-]+$/;

function fail(path: string): never {
  throw new ApiAccountConfigError(
    `Invalid advanced_config field: ${path}`,
    path,
  );
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

function syntaxPosition(raw: string, error: unknown) {
  const match =
    error instanceof Error ? error.message.match(/position\s+(\d+)/i) : null;
  const offset = match ? Number(match[1]) : Math.max(0, raw.length - 1);
  const before = raw.slice(0, offset);
  const lines = before.split("\n");
  return { line: lines.length, column: (lines.at(-1)?.length ?? 0) + 1 };
}

export function normalizeApiAccountConfig(
  value: unknown,
  fallbackModel = "",
): ApiAccountAdvancedConfig {
  if (!isObject(value)) fail("root");
  const source = clone(value);
  const version = source.version ?? 1;
  if (version !== 1) fail("version");

  const mappingValue = source.model_mapping ?? {};
  if (!isObject(mappingValue)) fail("model_mapping");
  const modelMapping: Record<string, string> = {};
  for (const [alias, model] of Object.entries(mappingValue)) {
    if (!alias.trim() || typeof model !== "string" || !model.trim()) {
      fail(alias.trim() ? `model_mapping.${alias}` : "model_mapping");
    }
    modelMapping[alias.trim()] = model.trim();
  }

  const fallback = source.fallback_model ?? fallbackModel;
  if (typeof fallback !== "string") fail("fallback_model");
  const userAgent = source.user_agent ?? "";
  if (typeof userAgent !== "string" || /[\u0000-\u001f\u007f]/.test(userAgent))
    fail("user_agent");

  const headersValue = source.headers ?? {};
  if (!isObject(headersValue)) fail("headers");
  const headers: Record<string, string> = {};
  for (const [name, headerValue] of Object.entries(headersValue)) {
    const normalized = name.trim().toLowerCase().replaceAll("_", "-");
    const compact = normalized.replace(/[^a-z0-9]/g, "");
    if (
      !name.trim() ||
      !headerToken.test(name) ||
      typeof headerValue !== "string" ||
      protectedHeaders.has(normalized) ||
      protectedHeaderPrefixes.some((prefix) => normalized.startsWith(prefix)) ||
      compact.includes("apikey") ||
      compact.endsWith("subscriptionkey") ||
      /[\u0000-\u001f\u007f]/.test(headerValue)
    ) {
      fail(`headers.${name || "key"}`);
    }
    headers[name] = headerValue;
  }

  const bodyValue = source.body ?? {};
  if (!isObject(bodyValue)) fail("body");
  for (const field of Object.keys(bodyValue)) {
    if (protectedBody.has(field.toLowerCase().replace(/[^a-z0-9]/g, "")))
      fail(`body.${field}`);
  }

  return {
    ...source,
    version: 1,
    model_mapping: modelMapping,
    fallback_model: fallback.trim(),
    user_agent: userAgent,
    headers,
    body: clone(bodyValue),
  };
}

export function parseApiAccountConfig(raw: string): ApiAccountAdvancedConfig {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    const { line, column } = syntaxPosition(raw, error);
    throw new ApiAccountConfigError(
      `JSON syntax error at line ${line}, column ${column}`,
      "root",
      line,
      column,
    );
  }
  return normalizeApiAccountConfig(parsed);
}

export function formatApiAccountConfig(
  config: ApiAccountAdvancedConfig,
): string {
  return JSON.stringify(config, null, 2);
}

export function updateApiAccountConfig(
  config: ApiAccountAdvancedConfig,
  fields: Partial<
    Pick<
      ApiAccountAdvancedConfig,
      "model_mapping" | "fallback_model" | "user_agent" | "headers" | "body"
    >
  >,
): ApiAccountAdvancedConfig {
  return normalizeApiAccountConfig({ ...clone(config), ...clone(fields) });
}

export function stableApiAccountConfig(value: unknown): string {
  if (Array.isArray(value))
    return `[${value.map(stableApiAccountConfig).join(",")}]`;
  if (isObject(value))
    return `{${Object.keys(value)
      .sort()
      .map(
        (key) => `${JSON.stringify(key)}:${stableApiAccountConfig(value[key])}`,
      )
      .join(",")}}`;
  return JSON.stringify(value);
}
