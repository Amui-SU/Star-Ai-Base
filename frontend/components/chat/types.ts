"use client";

import type { ChatWebSearchStatus } from "@/lib/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  thinkingActive?: boolean;
  thinkingStartedAt?: number;
  thinkingDurationMs?: number;
  webSearchActive?: boolean;
  webSearchProgress?: string;
  sources?: Array<{
    bvid?: string;
    title: string;
    url: string;
    type?: "knowledge" | "web" | string;
  }>;
  webSearch?: ChatWebSearchStatus | null;
}

export type Reaction = "like" | "dislike" | null;

export interface ModelConfigProvider {
  provider: string;
  label: string;
  model: string;
  base_url?: string;
  enabled?: boolean;
  thinking_config?: Record<string, unknown>;
  thinking_template?: Record<string, unknown>;
}
