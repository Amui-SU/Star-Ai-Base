export type ProviderPreset = {
  provider: string;
  label: string;
  baseUrl: string;
  model: string;
  logo?: string;
  kind: "llm" | "search";
  protocol: "openai_compatible" | "anthropic_messages" | null;
  authScheme: "bearer" | "x_api_key" | null;
  websiteUrl: string;
  sections: Array<"identity" | "connection" | "models" | "request" | "json">;
};

const llmMetadata = {
  protocol: "openai_compatible" as const,
  authScheme: "bearer" as const,
  sections: [
    "identity",
    "connection",
    "models",
    "request",
    "json",
  ] as ProviderPreset["sections"],
};

export const PROVIDER_PRESETS: ProviderPreset[] = [
  {
    provider: "deepseek",
    label: "DeepSeek",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
    logo: "/logos/deepseek-icon.png",
    kind: "llm",
    ...llmMetadata,
    websiteUrl: "https://www.deepseek.com/",
  },
  {
    provider: "dashscope",
    label: "阿里云 DashScope",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-max",
    logo: "/logos/dashscope-icon.png",
    kind: "llm",
    ...llmMetadata,
    websiteUrl: "https://www.aliyun.com/product/bailian",
  },
  {
    provider: "openai",
    label: "OpenAI",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
    logo: "/logos/openai-icon.png",
    kind: "llm",
    ...llmMetadata,
    websiteUrl: "https://openai.com/",
  },
  {
    provider: "agnes",
    label: "Agnes",
    baseUrl: "https://apihub.agnes-ai.com/v1",
    model: "agnes-2.0-flash",
    logo: "/logos/agnes-icon.svg",
    kind: "llm",
    ...llmMetadata,
    websiteUrl: "https://agnes-ai.com/",
  },
  {
    provider: "claude",
    label: "Claude",
    baseUrl: "https://api.anthropic.com/v1",
    model: "claude-haiku-4-5",
    kind: "llm",
    ...llmMetadata,
    protocol: "anthropic_messages",
    authScheme: "x_api_key",
    websiteUrl: "https://www.anthropic.com/",
  },
  {
    provider: "kimi",
    label: "Moonshot Kimi",
    baseUrl: "https://api.moonshot.cn/v1",
    model: "moonshot-v1-8k",
    logo: "/logos/kimi-icon.png",
    kind: "llm",
    ...llmMetadata,
    websiteUrl: "https://www.moonshot.cn/",
  },
  {
    provider: "siliconflow",
    label: "SiliconFlow",
    baseUrl: "https://api.siliconflow.cn/v1",
    model: "Qwen/Qwen2.5-7B-Instruct",
    logo: "/logos/siliconflow-icon.png",
    kind: "llm",
    ...llmMetadata,
    websiteUrl: "https://siliconflow.cn/",
  },
  {
    provider: "zhipu",
    label: "智谱 GLM",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    model: "glm-4-flash",
    logo: "/logos/zhipu-icon.png",
    kind: "llm",
    ...llmMetadata,
    websiteUrl: "https://www.bigmodel.cn/",
  },
  {
    provider: "tavily",
    label: "Tavily 搜索",
    baseUrl: "https://api.tavily.com",
    model: "tavily-search",
    kind: "search",
    protocol: null,
    authScheme: null,
    websiteUrl: "https://tavily.com/",
    sections: ["identity", "connection"],
  },
];

export const providerPresetMap = new Map(
  PROVIDER_PRESETS.map((preset) => [preset.provider, preset]),
);

const LLM_PROVIDER_ORDER = [
  "dashscope",
  "deepseek",
  "openai",
  "agnes",
  "claude",
  "kimi",
  "siliconflow",
  "zhipu",
] as const;

export const LLM_PROVIDER_PRESETS = LLM_PROVIDER_ORDER.map((provider) => {
  const preset = providerPresetMap.get(provider);
  if (!preset) {
    throw new Error(`Missing provider preset: ${provider}`);
  }
  return preset;
});

export const providerLogoMap = new Map(
  LLM_PROVIDER_PRESETS.flatMap((preset) =>
    preset.logo ? [[preset.provider, preset.logo] as const] : [],
  ),
);
