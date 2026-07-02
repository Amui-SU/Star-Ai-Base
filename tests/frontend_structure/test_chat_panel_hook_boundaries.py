from .helpers import get_project_root


def test_chat_panel_uses_model_settings_hook():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    hook_file = (
        project_root / "frontend" / "components" / "chat" / "useChatModelSettings.ts"
    )

    assert hook_file.exists()
    assert "@/components/chat/useChatModelSettings" in chat_panel
    assert "formatThinkingConfig" not in chat_panel
    assert "inferThinkingMode" not in chat_panel
    assert "parseThinkingConfig" not in chat_panel
    assert "LLM_PROVIDER_PRESETS" not in chat_panel
    assert "chatApi.getModelConfig" not in chat_panel
    assert "chatApi.health" not in chat_panel
    assert "chatApi.setModelProvider" not in chat_panel
    assert "chatApi.saveModelProviderConfig" not in chat_panel


def test_chat_model_settings_hook_uses_state_helpers():
    project_root = get_project_root()
    hook_file = (
        project_root / "frontend" / "components" / "chat" / "useChatModelSettings.ts"
    )
    state_helper = (
        project_root / "frontend" / "components" / "chat" / "chatModelSettingsState.ts"
    )

    assert state_helper.exists()
    hook_source = hook_file.read_text(encoding="utf-8")
    helper_source = state_helper.read_text(encoding="utf-8")

    for helper_name in [
        "resolveCurrentApiSource",
        "resolveSourceAvailability",
        "buildModelSourceOptions",
        "buildProvidersForMenu",
        "hasEnabledCurrentSource",
        "shouldShowAiKeyHint",
    ]:
        assert f"export function {helper_name}" in helper_source
        assert helper_name in hook_source
        assert f"function {helper_name}" not in hook_source

    assert 'from "@/components/chat/chatModelSettingsState"' in hook_source
    assert "LLM_PROVIDER_PRESETS" not in hook_source
    assert "new Map(remoteProviders.map" not in hook_source


def test_chat_panel_uses_web_search_settings_hook():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    hook_file = (
        project_root
        / "frontend"
        / "components"
        / "chat"
        / "useChatWebSearchSettings.ts"
    )

    assert hook_file.exists()
    assert "@/components/chat/useChatWebSearchSettings" in chat_panel
    assert "chatApi.getWebSearchConfig" not in chat_panel
    assert "chatApi.saveWebSearchConfig" not in chat_panel
    assert "webSearchConfigOpen, setWebSearchConfigOpen" not in chat_panel
    assert "webSearchApiKey, setWebSearchApiKey" not in chat_panel
    assert "webSearchConfigSaving, setWebSearchConfigSaving" not in chat_panel
    assert "webSearchConfigError, setWebSearchConfigError" not in chat_panel


def test_chat_panel_uses_conversation_history_hook():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    hook_file = (
        project_root
        / "frontend"
        / "components"
        / "chat"
        / "useChatConversationHistory.ts"
    )

    assert hook_file.exists()
    assert "@/components/chat/useChatConversationHistory" in chat_panel
    assert "chatHistoryApi" not in chat_panel
    assert "currentConversationId, setCurrentConversationId" not in chat_panel
    assert "lastConversationRequestKeyRef" not in chat_panel
    assert "lastNewConversationRequestKeyRef" not in chat_panel
    assert "scopeToHistoryScope" not in chat_panel
    assert "historyScopeToSelection" not in chat_panel
    assert "persistConversation" not in chat_panel
    assert "handleOpenConversation" not in chat_panel
    assert "handleNewConversation" not in chat_panel


def test_chat_panel_uses_knowledge_context_hook():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    hook_file = (
        project_root / "frontend" / "components" / "chat" / "useChatKnowledgeContext.ts"
    )

    assert hook_file.exists()
    hook_source = hook_file.read_text(encoding="utf-8")
    assert "export function useChatKnowledgeContext" in hook_source
    assert "@/components/chat/useChatKnowledgeContext" in chat_panel
    assert "knowledgeBaseApi.stats" not in chat_panel
    assert "knowledgeBaseApi.getScopeOptions" not in chat_panel
    assert "stats, setStats" not in chat_panel
    assert "scopeOptions, setScopeOptions" not in chat_panel
    assert "chatScope, setChatScope" not in chat_panel
    assert "useState<KnowledgeStats" not in chat_panel
    assert "useState<KnowledgeScopeOptions" not in chat_panel
    assert "useState<ChatScopeSelection" not in chat_panel


def test_chat_panel_uses_viewport_hook():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    hook_file = (
        project_root / "frontend" / "components" / "chat" / "useChatPanelViewport.ts"
    )

    assert hook_file.exists()
    hook_source = hook_file.read_text(encoding="utf-8")
    assert "export function useChatPanelViewport" in hook_source
    assert "@/components/chat/useChatPanelViewport" in chat_panel
    for token in [
        "CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD_PX",
        "isNearScrollBottom",
        "requestAnimationFrame",
        "cancelAnimationFrame",
        "scrollIntoView",
        "scrollHeight",
        "style.height",
        "style.overflowY",
        "adjustComposerHeight",
    ]:
        assert token not in chat_panel
    assert "const handleChatScroll" not in chat_panel
    assert "const handleComposerChange" not in chat_panel
