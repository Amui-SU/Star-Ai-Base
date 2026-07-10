export type ProviderPreset = {
  provider: string;
  label: string;
  baseUrl: string;
  model: string;
  logo?: string;
  kind: "llm" | "search";
};

export const PROVIDER_PRESETS: ProviderPreset[] = [
  {
    provider: "deepseek",
    label: "DeepSeek",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
    logo: "/logos/deepseek-icon.png",
    kind: "llm",
  },
  {
    provider: "dashscope",
    label: "阿里云 DashScope",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-max",
    logo: "/logos/dashscope-icon.png",
    kind: "llm",
  },
  {
    provider: "openai",
    label: "OpenAI",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
    logo: "/logos/openai-icon.png",
    kind: "llm",
  },
  {
    provider: "agnes",
    label: "Agnes",
    baseUrl: "https://apihub.agnes-ai.com/v1",
    model: "agnes-2.0-flash",
    kind: "llm",
  },
  {
    provider: "claude",
    label: "Claude",
    baseUrl: "https://api.anthropic.com/v1",
    model: "claude-haiku-4-5",
    kind: "llm",
  },
  {
    provider: "kimi",
    label: "Moonshot Kimi",
    baseUrl: "https://api.moonshot.cn/v1",
    model: "moonshot-v1-8k",
    logo: "/logos/kimi-icon.png",
    kind: "llm",
  },
  {
    provider: "siliconflow",
    label: "SiliconFlow",
    baseUrl: "https://api.siliconflow.cn/v1",
    model: "Qwen/Qwen2.5-7B-Instruct",
    logo: "/logos/siliconflow-icon.png",
    kind: "llm",
  },
  {
    provider: "zhipu",
    label: "智谱 GLM",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    model: "glm-4-flash",
    logo: "/logos/zhipu-icon.png",
    kind: "llm",
  },
  {
    provider: "tavily",
    label: "Tavily 搜索",
    baseUrl: "https://api.tavily.com",
    model: "tavily-search",
    kind: "search",
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
