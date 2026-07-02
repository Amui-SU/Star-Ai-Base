"use client";

import Composer from "@/components/chat/Composer";
import type {
  KnowledgeScopeOptions,
  WebSearchConfigResponse,
  WebSearchProvider,
} from "@/lib/api";
import type { ChatScopeSelection } from "@/lib/chatScope";

interface ChatPanelComposerSectionProps {
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  input: string;
  knowledgeBaseId?: number | null;
  isGenerating: boolean;
  canSend: boolean;
  scopeNotice: string;
  scopeOptions: KnowledgeScopeOptions;
  chatScope: ChatScopeSelection;
  webSearchEnabled: boolean;
  webSearchProvider: WebSearchProvider;
  webSearchConfig: WebSearchConfigResponse | null;
  canConfigureWebSearch: boolean;
  webSearchNotice: string;
  onInputChange: (value: string, element: HTMLTextAreaElement) => void;
  onSendQuestion: (question: string) => void;
  onStopGenerating: () => void;
  onScopeChange: (next: ChatScopeSelection) => void;
  onWebSearchChange: (enabled: boolean) => void;
  onWebSearchProviderChange: (provider: WebSearchProvider) => void;
  onConfigureTavily: () => void;
}

export default function ChatPanelComposerSection({
  inputRef,
  input,
  knowledgeBaseId,
  isGenerating,
  canSend,
  scopeNotice,
  scopeOptions,
  chatScope,
  webSearchEnabled,
  webSearchProvider,
  webSearchConfig,
  canConfigureWebSearch,
  webSearchNotice,
  onInputChange,
  onSendQuestion,
  onStopGenerating,
  onScopeChange,
  onWebSearchChange,
  onWebSearchProviderChange,
  onConfigureTavily,
}: ChatPanelComposerSectionProps) {
  return (
    <div className="panel-footer border-transparent bg-transparent flex flex-col items-center gap-2">
      <div className="w-full max-w-3xl mx-auto mt-1">
        {scopeNotice && (
          <div className="scope-notice" aria-live="polite">
            {scopeNotice}
          </div>
        )}
        <Composer
          inputRef={inputRef}
          input={input}
          knowledgeBaseId={knowledgeBaseId}
          isGenerating={isGenerating}
          canSend={canSend}
          scopeOptions={scopeOptions}
          chatScope={chatScope}
          webSearchEnabled={webSearchEnabled}
          webSearchProvider={webSearchProvider}
          webSearchConfig={webSearchConfig}
          canConfigureWebSearch={canConfigureWebSearch}
          webSearchNotice={webSearchNotice}
          onInputChange={onInputChange}
          onSend={() => onSendQuestion(input)}
          onStopGenerating={onStopGenerating}
          onScopeChange={onScopeChange}
          onWebSearchChange={onWebSearchChange}
          onWebSearchProviderChange={onWebSearchProviderChange}
          onConfigureTavily={onConfigureTavily}
        />
      </div>
      <div className="composer-disclaimer text-[10px] text-(--muted) text-center">
        内容由 AI 生成，请注意甄别。
      </div>
    </div>
  );
}
