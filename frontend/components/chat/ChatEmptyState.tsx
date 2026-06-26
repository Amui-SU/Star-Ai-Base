"use client";

const EMPTY_PROMPTS = [
  "总结收藏夹里最有价值的内容",
  "有哪些适合快速复习的系列？",
  "列出与某个主题相关的视频并给出关键点",
  "按主题整理我的收藏夹内容",
  "用一句话概括每个视频的重点",
  "推荐3个最适合入门的学习视频",
];

interface ChatEmptyStateProps {
  showAiKeyHint: boolean;
  onOpenApiAccounts?: () => void;
  onPromptSelect: (prompt: string) => void;
}

export default function ChatEmptyState({
  showAiKeyHint,
  onOpenApiAccounts,
  onPromptSelect,
}: ChatEmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-hero">
        <h1 className="empty-hero-title">探索你的收藏</h1>
        <p className="empty-hero-copy">
          基于当前提问范围回答，可切换整个知识库、收藏夹或单个视频。
        </p>
      </div>
      {showAiKeyHint && (
        <div className="api-account-empty-hint">
          <div>
            <strong>先添加 AI 服务密钥</strong>
            <span>聊天和联网搜索会使用你自己保存的第三方 Key。</span>
          </div>
          {onOpenApiAccounts && (
            <button type="button" onClick={onOpenApiAccounts}>
              配置密钥
            </button>
          )}
        </div>
      )}
      <div className="prompt-grid">
        {EMPTY_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onPromptSelect(prompt)}
            className="prompt-chip"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
