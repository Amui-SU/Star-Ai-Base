"use client";

import Image from "next/image";
import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";

import type { LLMApiSource, LLMConfigResponse, LLMProvider } from "@/lib/api";
import { providerLogoMap } from "@/lib/providers";
import type {
  ModelMenuProvider,
  ModelSourceOption,
} from "@/components/chat/chatModelSettingsState";

interface ChatModelStatusProps {
  activeProvider: ModelMenuProvider | undefined;
  currentApiSource: LLMApiSource;
  currentProvider: string;
  isAdmin: boolean;
  llmChecking: boolean;
  llmConfig: LLMConfigResponse | null;
  llmSwitching: boolean;
  menuOpen: boolean;
  modelLatencyText: string;
  modelReady: boolean;
  modelStatusTitle: string;
  providers: ModelMenuProvider[];
  setMenuOpen: Dispatch<SetStateAction<boolean>>;
  sourceOptions: ModelSourceOption[];
  onConfigureProvider: (provider: ModelMenuProvider) => void;
  onProviderBlocked: (provider: ModelMenuProvider) => void;
  onSwitchModelSource: (apiSource: LLMApiSource) => void;
  onSwitchProvider: (provider: LLMProvider) => void;
}

export default function ChatModelStatus({
  activeProvider,
  currentApiSource,
  currentProvider,
  isAdmin,
  llmChecking,
  llmConfig,
  llmSwitching,
  menuOpen,
  modelLatencyText,
  modelReady,
  modelStatusTitle,
  providers,
  setMenuOpen,
  sourceOptions,
  onConfigureProvider,
  onProviderBlocked,
  onSwitchModelSource,
  onSwitchProvider,
}: ChatModelStatusProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onClickOutside = (event: MouseEvent) => {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [menuOpen, setMenuOpen]);

  return (
    <div className="model-status-card">
      <div className="relative" ref={menuRef}>
        <button
          type="button"
          disabled={llmSwitching}
          onClick={() => setMenuOpen((open) => !open)}
          className={`model-selector-trigger ${
            llmChecking ? "empty" : modelReady ? "ok" : "alert"
          }`}
          title={modelStatusTitle}
          aria-label="模型选择"
        >
          <Image
            src={
              activeProvider
                ? providerLogoMap.get(activeProvider.provider) ||
                  "/logos/qwen-icon.png"
                : "/logos/qwen-icon.png"
            }
            alt={activeProvider ? `${activeProvider.label} logo` : "model logo"}
            width={16}
            height={16}
            unoptimized
            className="model-health-logo"
          />
          <span className="model-latency">{modelLatencyText}</span>
        </button>

        {menuOpen && (
          <div className="model-provider-menu">
            <div className="model-source-switch" aria-label="模型来源">
              {sourceOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  aria-label={option.label}
                  aria-pressed={currentApiSource === option.value}
                  disabled={llmSwitching || !llmConfig || !option.enabled}
                  className={`model-source-option ${
                    currentApiSource === option.value ? "active" : ""
                  }`}
                  onClick={() => onSwitchModelSource(option.value)}
                  title={`${option.label} · ${option.hint}`}
                >
                  <span>{option.label}</span>
                  <small>{option.hint}</small>
                </button>
              ))}
            </div>
            {providers.map((provider) => (
              <div key={provider.provider} className="model-provider-row">
                <button
                  type="button"
                  disabled={
                    llmSwitching ||
                    !llmConfig ||
                    (!isAdmin && !provider.enabled)
                  }
                  onClick={() => {
                    if (!isAdmin) {
                      onProviderBlocked(provider);
                      setMenuOpen(false);
                      return;
                    }
                    if (provider.enabled) {
                      onSwitchProvider(provider.provider);
                    } else {
                      onConfigureProvider(provider);
                    }
                    setMenuOpen(false);
                  }}
                  className={`model-provider-option ${
                    provider.provider === currentProvider ? "active" : ""
                  }`}
                  title={
                    provider.enabled
                      ? `${provider.label} · ${provider.model}`
                      : `${provider.label}（${
                          currentApiSource === "official" ? "未开通" : "未配置"
                        }）`
                  }
                >
                  <span className="inline-flex min-w-0 flex-1 items-center gap-1.5">
                    <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-(--paper)">
                      <Image
                        src={
                          providerLogoMap.get(provider.provider) ||
                          "/logos/qwen-icon.png"
                        }
                        alt={`${provider.label} logo`}
                        width={12}
                        height={12}
                        unoptimized
                        className="rounded-sm object-contain"
                      />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-[10px] font-semibold text-(--ink-soft) leading-tight truncate">
                        {provider.label}
                      </span>
                      <span className="block text-[9px] text-(--muted) leading-tight truncate mt-1">
                        {provider.model}
                      </span>
                    </span>
                  </span>
                  <span
                    className={`status-pill ${
                      provider.enabled
                        ? provider.provider === currentProvider
                          ? "ok"
                          : "empty"
                        : "partial"
                    }`}
                  >
                    {provider.enabled
                      ? provider.provider === currentProvider
                        ? "当前"
                        : "可用"
                      : currentApiSource === "official"
                        ? "未开通"
                        : "未配置"}
                  </span>
                </button>
                {provider.enabled && isAdmin && (
                  <button
                    type="button"
                    className="model-provider-config-btn"
                    onClick={() => onConfigureProvider(provider)}
                    title={`配置 ${provider.label}`}
                    aria-label={`配置 ${provider.label}`}
                  >
                    配置
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
