from .helpers import get_project_root


def test_chat_panel_uses_chat_subcomponents():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    composer_section = (
        project_root
        / "frontend"
        / "components"
        / "chat"
        / "ChatPanelComposerSection.tsx"
    ).read_text(encoding="utf-8")

    for relative_path in [
        "frontend/components/chat/MessageList.tsx",
        "frontend/components/chat/Composer.tsx",
        "frontend/components/chat/ChatPanelComposerSection.tsx",
        "frontend/components/chat/WebSearchConfigModal.tsx",
        "frontend/components/chat/ModelConfigModal.tsx",
        "frontend/components/chat/useChatStreaming.ts",
        "frontend/components/chat/ChatEmptyState.tsx",
    ]:
        assert (project_root / relative_path).exists()

    assert "@/components/chat/MessageList" in chat_panel
    assert "@/components/chat/ChatPanelComposerSection" in chat_panel
    assert "@/components/chat/Composer" not in chat_panel
    assert "@/components/chat/Composer" in composer_section
    assert "@/components/chat/WebSearchConfigModal" in chat_panel
    assert "@/components/chat/ModelConfigModal" in chat_panel
    assert "@/components/chat/useChatStreaming" in chat_panel
    assert "@/components/chat/ChatEmptyState" in chat_panel
    assert "provider-config-body" not in chat_panel
    assert "thinking-config-fieldset" not in chat_panel
    assert "鎺㈢储浣犵殑鏀惰棌" not in chat_panel
    assert "鎬荤粨鏀惰棌澶归噷鏈€鏈変环鍊肩殑鍐呭" not in chat_panel


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


def test_chat_panel_model_status_menu_is_extracted():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    header_component = (
        project_root / "frontend" / "components" / "chat" / "ChatPanelHeader.tsx"
    ).read_text(encoding="utf-8")
    status_component = (
        project_root / "frontend" / "components" / "chat" / "ChatModelStatus.tsx"
    )

    assert status_component.exists()
    assert "@/components/chat/ChatPanelHeader" in chat_panel
    assert "@/components/chat/ChatModelStatus" not in chat_panel
    assert "@/components/chat/ChatModelStatus" in header_component
    assert 'from "next/image"' not in chat_panel
    assert "@/lib/providers" not in chat_panel
    assert "modelMenuRef" not in chat_panel
    assert "model-provider-menu" not in chat_panel
    assert "model-source-switch" not in chat_panel


def test_chat_panel_uses_header_section_component():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    header_file = (
        project_root / "frontend" / "components" / "chat" / "ChatPanelHeader.tsx"
    )

    assert header_file.exists()
    header_source = header_file.read_text(encoding="utf-8")
    assert "export default function ChatPanelHeader" in header_source
    assert "@/components/chat/ChatPanelHeader" in chat_panel
    assert "@/components/chat/ChatModelStatus" not in chat_panel
    assert "@/components/chat/ChatModelStatus" in header_source
    assert "chat-context-row" not in chat_panel
    assert "chat-context-actions" not in chat_panel
    assert "chat-kb-context" not in chat_panel
    assert "chat-kb-meta" not in chat_panel


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


def test_chat_panel_uses_composer_section_component():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    section_file = (
        project_root
        / "frontend"
        / "components"
        / "chat"
        / "ChatPanelComposerSection.tsx"
    )

    assert section_file.exists()
    section_source = section_file.read_text(encoding="utf-8")
    assert "export default function ChatPanelComposerSection" in section_source
    assert "@/components/chat/ChatPanelComposerSection" in chat_panel
    assert "panel-footer border-transparent" not in chat_panel
    assert "scope-notice" not in chat_panel
    assert "composer-disclaimer" not in chat_panel
    assert "<Composer" not in chat_panel


def test_chat_streaming_uses_state_helpers():
    project_root = get_project_root()
    hook_file = (
        project_root / "frontend" / "components" / "chat" / "useChatStreaming.ts"
    )
    state_helper = (
        project_root / "frontend" / "components" / "chat" / "chatStreamingState.ts"
    )

    assert state_helper.exists()
    hook_source = hook_file.read_text(encoding="utf-8")
    helper_source = state_helper.read_text(encoding="utf-8")

    for helper_name in [
        "extractThinkingFromContent",
        "updateAssistantMessage",
        "startAssistantStreaming",
        "applyParsedStreamUpdate",
        "finalizeStreamedAssistantAnswer",
        "finalizeFallbackAssistantAnswer",
        "applyAssistantError",
        "resetAssistantForRegeneration",
    ]:
        assert f"export function {helper_name}" in helper_source
        assert helper_name in hook_source

    assert 'from "@/components/chat/chatStreamingState"' in hook_source
    assert "function extractThinkingFromContent" not in hook_source
    assert "interface ThinkingExtraction" not in hook_source
    assert "prev.map((m)" not in hook_source
    assert "prev.map((message)" not in hook_source


def test_message_list_uses_focused_subcomponents():
    project_root = get_project_root()
    message_list = (
        project_root / "frontend" / "components" / "chat" / "MessageList.tsx"
    ).read_text(encoding="utf-8")

    for relative_path in [
        "frontend/components/chat/MessageSources.tsx",
        "frontend/components/chat/MessageActions.tsx",
    ]:
        assert (project_root / relative_path).exists()

    assert "@/components/chat/MessageSources" in message_list
    assert "@/components/chat/MessageActions" in message_list
    assert "function CopyIcon" not in message_list
    assert "source-details" not in message_list
    assert "web-search-error-list" not in message_list
    assert 'aria-label="回答操作"' not in message_list
    assert 'aria-label="问题操作"' not in message_list


def test_chat_scope_picker_uses_focused_subcomponents():
    project_root = get_project_root()
    picker = (
        project_root / "frontend" / "components" / "ChatScopePicker.tsx"
    ).read_text(encoding="utf-8")

    for relative_path in [
        "frontend/components/chat-scope/ChatScopeTrigger.tsx",
        "frontend/components/chat-scope/ScopeWebSearchPanel.tsx",
        "frontend/components/chat-scope/ScopeModeGrid.tsx",
        "frontend/components/chat-scope/ScopeFolderSection.tsx",
        "frontend/components/chat-scope/ScopeVideoSearchSection.tsx",
    ]:
        assert (project_root / relative_path).exists()

    for import_path in [
        "@/components/chat-scope/ChatScopeTrigger",
        "@/components/chat-scope/ScopeWebSearchPanel",
        "@/components/chat-scope/ScopeModeGrid",
        "@/components/chat-scope/ScopeFolderSection",
        "@/components/chat-scope/ScopeVideoSearchSection",
    ]:
        assert import_path in picker

    for token in [
        "scope-web-provider-panel",
        "scope-mode-grid",
        "scope-folder-row",
        "scope-video-list",
        "scope-web-search-privacy",
    ]:
        assert token not in picker


def test_chat_panel_history_tests_are_split_from_main_suite():
    project_root = get_project_root()
    main_test = project_root / "frontend" / "components" / "ChatPanel.test.tsx"
    history_test = (
        project_root / "frontend" / "components" / "ChatPanel.history.test.tsx"
    )
    test_utils = (
        project_root / "frontend" / "components" / "chat" / "chatPanelTestUtils.tsx"
    )

    main_source = main_test.read_text(encoding="utf-8")

    assert history_test.exists()
    assert test_utils.exists()
    assert (
        "opens a requested conversation from the expanded history panel"
        not in main_source
    )
    assert (
        "starts a new conversation from an expanded-page request without deleting saved history"
        not in main_source
    )

    history_source = history_test.read_text(encoding="utf-8")
    assert (
        "opens a requested conversation from the expanded history panel"
        in history_source
    )
    assert (
        "starts a new conversation from an expanded-page request without deleting saved history"
        in history_source
    )
    assert "@/components/chat/chatPanelTestUtils" in main_source
    assert "@/components/chat/chatPanelTestUtils" in history_source


def test_chat_panel_streaming_tests_are_split_from_main_suite():
    project_root = get_project_root()
    main_test = project_root / "frontend" / "components" / "ChatPanel.test.tsx"
    streaming_test = (
        project_root / "frontend" / "components" / "ChatPanel.streaming.test.tsx"
    )

    moved_tests = [
        "keeps a streaming response alive after the old fixed deadline when content arrived",
        "uses instant autoscroll during streaming updates to avoid repeated smooth-scroll jank",
        "does not force autoscroll while the user reads earlier content during streaming",
        "does not call the non-stream fallback after idle timeout when partial content exists",
    ]
    main_source = main_test.read_text(encoding="utf-8")

    assert streaming_test.exists()
    streaming_source = streaming_test.read_text(encoding="utf-8")
    assert "@/components/chat/chatPanelTestUtils" in streaming_source

    for test_name in moved_tests:
        assert test_name not in main_source
        assert test_name in streaming_source


def test_chat_panel_web_search_tests_are_split_from_main_suite():
    project_root = get_project_root()
    main_test = project_root / "frontend" / "components" / "ChatPanel.test.tsx"
    web_search_test = (
        project_root / "frontend" / "components" / "ChatPanel.web-search.test.tsx"
    )

    moved_tests = [
        "sends the web search flag when the picker toggle is enabled",
        "resets the web search provider to auto when enabling search from the picker",
        "opens Tavily config from web search provider choice and sends Tavily after saving",
        "shows the web search notice only on the scope chip and then restores the scope text",
    ]
    main_source = main_test.read_text(encoding="utf-8")

    assert web_search_test.exists()
    web_search_source = web_search_test.read_text(encoding="utf-8")
    assert "@/components/chat/chatPanelTestUtils" in web_search_source

    for test_name in moved_tests:
        assert test_name not in main_source
        assert test_name in web_search_source


def test_chat_panel_web_search_result_tests_are_split_from_toggle_suite():
    project_root = get_project_root()
    web_search_test = (
        project_root / "frontend" / "components" / "ChatPanel.web-search.test.tsx"
    )
    results_test = (
        project_root
        / "frontend"
        / "components"
        / "ChatPanel.web-search-results.test.tsx"
    )
    focused_dir = project_root / "frontend" / "components" / "chat" / "__tests__"
    focused_files = [
        focused_dir / "ChatPanel.web-search-sources.test.tsx",
        focused_dir / "ChatPanel.web-search-progress.test.tsx",
        focused_dir / "ChatPanel.web-search-status.test.tsx",
    ]

    moved_tests = [
        "labels knowledge and web sources in assistant references",
        "shows web sources from the streaming metadata in assistant references",
        "renders web search progress as a live status outside thinking text",
        "clears previous references immediately when regenerating an answer",
        "shows web search fallback status returned by the chat response",
        "shows attempted queries when web search returns no results",
    ]
    web_search_source = web_search_test.read_text(encoding="utf-8")

    assert results_test.exists()
    for focused_file in focused_files:
        assert focused_file.exists()
    focused_source = "\n".join(
        focused_file.read_text(encoding="utf-8") for focused_file in focused_files
    )
    assert "@/components/chat/chatPanelTestUtils" in focused_source

    for test_name in moved_tests:
        assert test_name not in web_search_source
        assert test_name in focused_source


def test_chat_panel_config_tests_are_split_from_main_suite():
    project_root = get_project_root()
    main_test = project_root / "frontend" / "components" / "ChatPanel.test.tsx"
    config_test = project_root / "frontend" / "components" / "ChatPanel.config.test.tsx"

    moved_tests = [
        "does not show the AI key prompt when a model is available",
        "lets users switch between official and personal model sources above the provider list",
        "treats legacy model config without an explicit source as official",
        "shows the AI key prompt only after config loads with no usable model",
        "places the knowledge-base meta next to the model selector",
        "hides global provider and Tavily configuration controls from regular users",
        "lets regular users open their own AI service key settings for Tavily",
    ]
    main_source = main_test.read_text(encoding="utf-8")

    assert config_test.exists()
    config_source = config_test.read_text(encoding="utf-8")
    assert "@/components/chat/chatPanelTestUtils" in config_source

    for test_name in moved_tests:
        assert test_name not in main_source
        assert test_name in config_source


def test_frontend_provider_presets_are_shared():
    project_root = get_project_root()
    providers_file = project_root / "frontend" / "lib" / "providers.ts"
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    chat_panel_header = (
        project_root / "frontend" / "components" / "chat" / "ChatPanelHeader.tsx"
    ).read_text(encoding="utf-8")
    chat_model_status = (
        project_root / "frontend" / "components" / "chat" / "ChatModelStatus.tsx"
    ).read_text(encoding="utf-8")
    api_accounts_panel = (
        project_root / "frontend" / "components" / "ApiAccountsPanel.tsx"
    ).read_text(encoding="utf-8")

    assert providers_file.exists()
    assert "@/components/chat/ChatPanelHeader" in chat_panel
    assert "@/components/chat/ChatModelStatus" in chat_panel_header
    assert "@/lib/providers" in chat_model_status
    assert "@/lib/providers" in api_accounts_panel
    assert "const PROVIDERS" not in api_accounts_panel
    assert "const builtInProviders" not in chat_panel
    assert "const providerLogoMap" not in chat_panel
