from .helpers import get_project_root


def test_chat_panel_uses_chat_subcomponents():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )

    for relative_path in [
        "frontend/components/chat/MessageList.tsx",
        "frontend/components/chat/Composer.tsx",
        "frontend/components/chat/WebSearchConfigModal.tsx",
        "frontend/components/chat/ModelConfigModal.tsx",
        "frontend/components/chat/useChatStreaming.ts",
        "frontend/components/chat/ChatEmptyState.tsx",
    ]:
        assert (project_root / relative_path).exists()

    assert "@/components/chat/MessageList" in chat_panel
    assert "@/components/chat/Composer" in chat_panel
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
    results_source = results_test.read_text(encoding="utf-8")
    assert "@/components/chat/chatPanelTestUtils" in results_source

    for test_name in moved_tests:
        assert test_name not in web_search_source
        assert test_name in results_source


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
    api_accounts_panel = (
        project_root / "frontend" / "components" / "ApiAccountsPanel.tsx"
    ).read_text(encoding="utf-8")

    assert providers_file.exists()
    assert "@/lib/providers" in chat_panel
    assert "@/lib/providers" in api_accounts_panel
    assert "const PROVIDERS" not in api_accounts_panel
    assert "const builtInProviders" not in chat_panel
    assert "const providerLogoMap" not in chat_panel


def test_common_modals_use_shared_shell():
    project_root = get_project_root()
    modal_shell = project_root / "frontend" / "components" / "ui" / "ModalShell.tsx"

    assert modal_shell.exists()
    for relative_path in [
        "frontend/components/AdminUsersPanel.tsx",
        "frontend/components/ApiAccountsPanel.tsx",
        "frontend/components/ImportModal.tsx",
        "frontend/components/LocalConnectionSettings.tsx",
        "frontend/components/OrganizePreviewModal.tsx",
        "frontend/components/UserMenu.tsx",
        "frontend/components/chat/ModelConfigModal.tsx",
        "frontend/components/chat/WebSearchConfigModal.tsx",
    ]:
        source = (project_root / relative_path).read_text(encoding="utf-8")
        assert "@/components/ui/ModalShell" in source
        assert 'className="modal-backdrop' not in source


def test_auth_demo_preview_is_extracted_from_auth_page():
    project_root = get_project_root()
    auth_page = (project_root / "frontend" / "components" / "AuthPage.tsx").read_text(
        encoding="utf-8"
    )

    assert (project_root / "frontend/components/auth/AuthDemoPreview.tsx").exists()
    assert (project_root / "frontend/components/auth/useAuthDemoPreview.ts").exists()
    assert "@/components/auth/AuthDemoPreview" in auth_page
    assert "const demoQuestion" not in auth_page
    assert "const demoAnswer" not in auth_page
    assert "setDemoStep" not in auth_page


def test_auth_page_form_logic_is_extracted():
    project_root = get_project_root()
    auth_page = (project_root / "frontend" / "components" / "AuthPage.tsx").read_text(
        encoding="utf-8"
    )

    assert (project_root / "frontend/components/auth/useAuthForm.ts").exists()
    assert (project_root / "frontend/components/auth/authPageLogic.ts").exists()
    assert "@/components/auth/useAuthForm" in auth_page
    assert "@/components/auth/authPageLogic" in auth_page
    assert "const CODE_COUNTDOWN" not in auth_page
    assert "const startCountdown" not in auth_page
    assert "const handleSendCode" not in auth_page
    assert "const handleRegister" not in auth_page
    assert "const isLocalhost" not in auth_page


def test_sources_video_player_portal_is_extracted():
    project_root = get_project_root()
    sources_panel = (
        project_root / "frontend" / "components" / "SourcesPanel.tsx"
    ).read_text(encoding="utf-8")

    assert (project_root / "frontend/components/sources/VideoPlayerPortal.tsx").exists()
    assert "@/components/sources/VideoPlayerPortal" in sources_panel
    assert "createPortal" not in sources_panel
    assert "player.bilibili.com" not in sources_panel


def test_sources_panel_pure_logic_is_extracted():
    project_root = get_project_root()
    sources_panel = (
        project_root / "frontend" / "components" / "SourcesPanel.tsx"
    ).read_text(encoding="utf-8")

    assert (project_root / "frontend/components/sources/sourcesPanelLogic.ts").exists()
    assert "@/components/sources/sourcesPanelLogic" in sources_panel
    assert "const formatTime" not in sources_panel
    assert "const getFolderStatus" not in sources_panel
    assert "const getButtonText" not in sources_panel


def test_sources_panel_data_loading_is_extracted():
    project_root = get_project_root()
    sources_panel = (
        project_root / "frontend" / "components" / "SourcesPanel.tsx"
    ).read_text(encoding="utf-8")
    hook_file = (
        project_root / "frontend" / "components" / "sources" / "useSourcesPanelData.ts"
    )

    assert hook_file.exists()
    assert "@/components/sources/useSourcesPanelData" in sources_panel
    assert "sourceBindingApi.getFavorites" not in sources_panel
    assert "knowledgeBaseApi.stats" not in sources_panel
    assert "const loadFolders" not in sources_panel
    assert "const loadStatuses" not in sources_panel


def test_sources_panel_knowledge_build_is_extracted():
    project_root = get_project_root()
    sources_panel = (
        project_root / "frontend" / "components" / "SourcesPanel.tsx"
    ).read_text(encoding="utf-8")
    hook_file = (
        project_root
        / "frontend"
        / "components"
        / "sources"
        / "useSourcesKnowledgeBuild.ts"
    )

    assert hook_file.exists()
    assert "@/components/sources/useSourcesKnowledgeBuild" in sources_panel
    assert "knowledgeBaseApi.build" not in sources_panel
    assert "knowledgeBaseApi.getBuildStatus" not in sources_panel
    assert "const buildKnowledge" not in sources_panel
    assert "const getSelectedVideoFolderIds" not in sources_panel


def test_sources_panel_actions_are_extracted():
    project_root = get_project_root()
    sources_panel = (
        project_root / "frontend" / "components" / "SourcesPanel.tsx"
    ).read_text(encoding="utf-8")
    hook_file = (
        project_root
        / "frontend"
        / "components"
        / "sources"
        / "useSourcesPanelActions.ts"
    )

    assert hook_file.exists()
    assert "@/components/sources/useSourcesPanelActions" in sources_panel
    assert "sourceBindingApi.updateVideoTitle" not in sources_panel
    assert "sourceBindingApi.getAllFavoriteVideos" not in sources_panel
    assert "sourceBindingApi.organizePreview" not in sources_panel
    assert "const saveVideoTitle" not in sources_panel
    assert "const openOrganizePreview" not in sources_panel
    assert "const toggleExpand" not in sources_panel


def test_workspace_state_is_extracted_from_home_page():
    project_root = get_project_root()
    page = (project_root / "frontend" / "app" / "page.tsx").read_text(encoding="utf-8")

    assert (project_root / "frontend/app/useWorkspaceState.ts").exists()
    assert "@/app/useWorkspaceState" in page
    assert "const getInitialSidebarOpen" not in page
    assert "const isMobileViewport" not in page
    assert 'localStorage.getItem("sidebar_width")' not in page
