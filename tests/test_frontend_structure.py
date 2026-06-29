import json
from pathlib import Path


def test_chat_panel_uses_chat_subcomponents():
    project_root = Path(__file__).resolve().parents[1]
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
    assert "探索你的收藏" not in chat_panel
    assert "总结收藏夹里最有价值的内容" not in chat_panel


def test_chat_panel_uses_model_settings_hook():
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
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


def test_frontend_api_delegates_client_and_system_auth_boundaries():
    project_root = Path(__file__).resolve().parents[1]
    api_file = project_root / "frontend" / "lib" / "api.ts"
    api_source = api_file.read_text(encoding="utf-8")

    for relative_path in [
        "frontend/lib/api/client.ts",
        "frontend/lib/api/systemAuth.ts",
        "frontend/lib/api/systemAuthTypes.ts",
    ]:
        assert (project_root / relative_path).exists()

    assert 'from "./api/client"' in api_source
    assert 'from "./api/systemAuth"' in api_source
    assert 'from "./api/systemAuthTypes"' in api_source
    assert "function withQuery" not in api_source
    assert "export async function request" not in api_source
    assert "export const systemAuthApi" not in api_source
    assert "clearLocalSessionToken" not in api_source
    assert "saveLocalSessionToken" not in api_source


def test_frontend_api_delegates_account_and_source_boundaries():
    project_root = Path(__file__).resolve().parents[1]
    api_file = project_root / "frontend" / "lib" / "api.ts"
    api_source = api_file.read_text(encoding="utf-8")

    for relative_path in [
        "frontend/lib/api/apiAccounts.ts",
        "frontend/lib/api/apiAccountTypes.ts",
        "frontend/lib/api/sourceBindings.ts",
        "frontend/lib/api/sourceTypes.ts",
    ]:
        assert (project_root / relative_path).exists()

    assert 'from "./api/apiAccounts"' in api_source
    assert 'from "./api/apiAccountTypes"' in api_source
    assert 'from "./api/sourceBindings"' in api_source
    assert 'from "./api/sourceTypes"' in api_source
    assert "export const apiAccountApi" not in api_source
    assert "export const sourceBindingApi" not in api_source
    assert "export interface ApiAccount" not in api_source
    assert "export interface SourceBinding" not in api_source
    assert "export interface FavoriteFolder" not in api_source
    assert "export interface Video" not in api_source


def test_frontend_api_delegates_import_favorites_and_legacy_boundaries():
    project_root = Path(__file__).resolve().parents[1]
    api_file = project_root / "frontend" / "lib" / "api.ts"
    api_source = api_file.read_text(encoding="utf-8")

    for relative_path in [
        "frontend/lib/api/imports.ts",
        "frontend/lib/api/importTypes.ts",
        "frontend/lib/api/legacyAuth.ts",
        "frontend/lib/api/favorites.ts",
        "frontend/lib/api/legacyKnowledge.ts",
        "frontend/lib/api/knowledgeTypes.ts",
    ]:
        assert (project_root / relative_path).exists()

    assert 'from "./api/imports"' in api_source
    assert 'from "./api/importTypes"' in api_source
    assert 'from "./api/legacyAuth"' in api_source
    assert 'from "./api/favorites"' in api_source
    assert 'from "./api/legacyKnowledge"' in api_source
    assert 'from "./api/knowledgeTypes"' in api_source
    assert "export const importApi" not in api_source
    assert "export const authApi" not in api_source
    assert "export const favoritesApi" not in api_source
    assert "export const knowledgeApi" not in api_source
    assert "export interface ImportMethod" not in api_source
    assert "export interface BuildStatus" not in api_source
    assert "export interface KnowledgeStats" not in api_source


def test_frontend_api_is_a_barrel_for_remaining_domain_modules():
    project_root = Path(__file__).resolve().parents[1]
    api_file = project_root / "frontend" / "lib" / "api.ts"
    api_source = api_file.read_text(encoding="utf-8")

    for relative_path in [
        "frontend/lib/api/chat.ts",
        "frontend/lib/api/chatHistory.ts",
        "frontend/lib/api/chatTypes.ts",
        "frontend/lib/api/knowledgeBases.ts",
        "frontend/lib/api/knowledgeBaseTypes.ts",
        "frontend/lib/api/localConnection.ts",
        "frontend/lib/api/localConnectionTypes.ts",
    ]:
        assert (project_root / relative_path).exists()

    assert 'from "./api/chat"' in api_source
    assert 'from "./api/chatHistory"' in api_source
    assert 'from "./api/chatTypes"' in api_source
    assert 'from "./api/knowledgeBases"' in api_source
    assert 'from "./api/knowledgeBaseTypes"' in api_source
    assert 'from "./api/localConnection"' in api_source
    assert 'from "./api/localConnectionTypes"' in api_source
    assert "export const " not in api_source
    assert "export interface " not in api_source
    assert "export type WebSearchProvider =" not in api_source
    assert "import { getApiBaseUrl, request }" not in api_source


def test_common_modals_use_shared_shell():
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
    auth_page = (project_root / "frontend" / "components" / "AuthPage.tsx").read_text(
        encoding="utf-8"
    )

    assert (project_root / "frontend/components/auth/AuthDemoPreview.tsx").exists()
    assert (project_root / "frontend/components/auth/useAuthDemoPreview.ts").exists()
    assert "@/components/auth/AuthDemoPreview" in auth_page
    assert "const demoQuestion" not in auth_page
    assert "const demoAnswer" not in auth_page
    assert "setDemoStep" not in auth_page


def test_sources_video_player_portal_is_extracted():
    project_root = Path(__file__).resolve().parents[1]
    sources_panel = (
        project_root / "frontend" / "components" / "SourcesPanel.tsx"
    ).read_text(encoding="utf-8")

    assert (project_root / "frontend/components/sources/VideoPlayerPortal.tsx").exists()
    assert "@/components/sources/VideoPlayerPortal" in sources_panel
    assert "createPortal" not in sources_panel
    assert "player.bilibili.com" not in sources_panel


def test_sources_panel_pure_logic_is_extracted():
    project_root = Path(__file__).resolve().parents[1]
    sources_panel = (
        project_root / "frontend" / "components" / "SourcesPanel.tsx"
    ).read_text(encoding="utf-8")

    assert (project_root / "frontend/components/sources/sourcesPanelLogic.ts").exists()
    assert "@/components/sources/sourcesPanelLogic" in sources_panel
    assert "const formatTime" not in sources_panel
    assert "const getFolderStatus" not in sources_panel
    assert "const getButtonText" not in sources_panel


def test_sources_panel_data_loading_is_extracted():
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
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
    project_root = Path(__file__).resolve().parents[1]
    page = (project_root / "frontend" / "app" / "page.tsx").read_text(encoding="utf-8")

    assert (project_root / "frontend/app/useWorkspaceState.ts").exists()
    assert "@/app/useWorkspaceState" in page
    assert "const getInitialSidebarOpen" not in page
    assert "const isMobileViewport" not in page
    assert 'localStorage.getItem("sidebar_width")' not in page


def test_frontend_build_cleans_next_dev_type_cache():
    project_root = Path(__file__).resolve().parents[1]
    package_json = json.loads(
        (project_root / "frontend" / "package.json").read_text(encoding="utf-8")
    )
    cleanup_script = project_root / "frontend" / "scripts" / "clean-next-dev-types.mjs"

    assert (
        package_json["scripts"]["prebuild"] == "node scripts/clean-next-dev-types.mjs"
    )
    assert cleanup_script.exists()
    cleanup_source = cleanup_script.read_text(encoding="utf-8")
    assert ".next/dev/types" in cleanup_source
    assert "rmdirSync" in cleanup_source


def test_global_styles_delegate_auth_styles_to_feature_file():
    project_root = Path(__file__).resolve().parents[1]
    globals_css = (project_root / "frontend" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )
    auth_css = project_root / "frontend" / "app" / "styles" / "auth.css"

    assert auth_css.exists()
    assert '@import "./styles/auth.css";' in globals_css
    assert "html.auth-page-active" not in globals_css
    assert ".auth-page" not in globals_css


def test_global_styles_delegate_modal_shell_styles_to_feature_file():
    project_root = Path(__file__).resolve().parents[1]
    globals_css = (project_root / "frontend" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )
    modals_css = project_root / "frontend" / "app" / "styles" / "modals.css"

    assert modals_css.exists()
    assert '@import "./styles/modals.css";' in globals_css
    assert "\n.modal-backdrop {" not in globals_css
    assert "\n.modal-card {" not in globals_css
    assert ".thinking-provider-modal" not in globals_css
    assert ".provider-config-body" not in globals_css


def test_global_styles_delegate_workspace_styles_to_feature_file():
    project_root = Path(__file__).resolve().parents[1]
    globals_css = (project_root / "frontend" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )
    workspace_css = project_root / "frontend" / "app" / "styles" / "workspace.css"

    assert workspace_css.exists()
    assert '@import "./styles/workspace.css";' in globals_css
    for selector in [
        "\n.app-shell {",
        "\n.workspace-card {",
        "\n.workspace-topbar {",
        "\n.workspace-sidebar-toggle {",
        "\n.sidebar-shell {",
        "\n.chat-history-sidebar-panel {",
        "\n.panel-chat-embedded {",
    ]:
        assert selector not in globals_css


def test_workspace_styles_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    styles_dir = project_root / "frontend" / "app" / "styles"
    workspace_css = (styles_dir / "workspace.css").read_text(encoding="utf-8")

    expected_imports = [
        "./workspace-shell.css",
        "./workspace-sidebar.css",
        "./workspace-history.css",
        "./workspace-chat-embedded.css",
        "./workspace-responsive-base.css",
        "./workspace-mobile-fullscreen.css",
    ]
    expected_anchors = {
        "workspace-shell.css": ".app-shell {",
        "workspace-sidebar.css": ".sidebar-shell {",
        "workspace-history.css": ".chat-history-sidebar-panel {",
        "workspace-chat-embedded.css": ".panel-chat-embedded .chat-scroll {",
        "workspace-responsive-base.css": "@media (max-width: 1024px)",
        "workspace-mobile-fullscreen.css": ".app-shell.sidebar-open .workspace-topbar",
    }

    for imported_path in expected_imports:
        imported_file = styles_dir / imported_path.removeprefix("./")
        assert imported_file.exists()
        assert expected_anchors[imported_file.name] in imported_file.read_text(
            encoding="utf-8"
        )
        assert f'@import "{imported_path}";' in workspace_css

    for selector in [
        "\n.app-shell {",
        "\n.sidebar-shell {",
        "\n.chat-history-sidebar-panel {",
        "\n.panel-chat-embedded .chat-scroll {",
        "\n@media (max-width: 1024px)",
        '\n@import "./workspace-responsive.css";',
    ]:
        assert selector not in workspace_css


def test_global_styles_delegate_account_panel_styles_to_feature_file():
    project_root = Path(__file__).resolve().parents[1]
    globals_css = (project_root / "frontend" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )
    account_css = project_root / "frontend" / "app" / "styles" / "account-panels.css"

    assert account_css.exists()
    assert '@import "./styles/account-panels.css";' in globals_css
    for selector in [
        "\n.user-menu {",
        "\n.user-menu-popover {",
        "\n.admin-users-panel {",
        "\n.local-connection-qr-card {",
        "\n.api-accounts-layout {",
        "\n.api-account-row {",
    ]:
        assert selector not in globals_css


def test_account_panel_styles_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    styles_dir = project_root / "frontend" / "app" / "styles"
    account_css = (styles_dir / "account-panels.css").read_text(encoding="utf-8")

    expected_imports = [
        "./user-menu.css",
        "./local-connection-qr.css",
        "./admin-users-panel.css",
        "./api-accounts-panel.css",
        "./account-panels-theme-overrides.css",
        "./api-account-empty-hint.css",
        "./local-connection-settings.css",
        "./account-panels-responsive.css",
    ]
    expected_anchors = {
        "user-menu.css": ".user-menu {",
        "local-connection-qr.css": ".local-connection-qr-card {",
        "admin-users-panel.css": ".admin-users-panel {",
        "api-accounts-panel.css": ".modal-card.api-accounts-panel {",
        "api-account-empty-hint.css": ".api-account-empty-hint {",
        "local-connection-settings.css": ".local-connection-trigger {",
        "account-panels-theme-overrides.css": "html.light .user-menu-popover {",
        "account-panels-responsive.css": "@media (max-width: 860px)",
    }

    for imported_path in expected_imports:
        imported_file = styles_dir / imported_path.removeprefix("./")
        assert imported_file.exists()
        assert expected_anchors[imported_file.name] in imported_file.read_text(
            encoding="utf-8"
        )
        assert f'@import "{imported_path}";' in account_css

    for selector in [
        "\n.user-menu {",
        "\n.local-connection-qr-card {",
        "\n.admin-users-panel {",
        "\n.modal-card.api-accounts-panel {",
        "\n.api-account-empty-hint {",
        "\n.local-connection-trigger {",
        "\nhtml.light .user-menu-popover {",
        "\n@media (max-width: 860px)",
    ]:
        assert selector not in account_css


def test_global_styles_delegate_sources_styles_to_feature_file():
    project_root = Path(__file__).resolve().parents[1]
    globals_css = (project_root / "frontend" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )
    sources_css = project_root / "frontend" / "app" / "styles" / "sources.css"

    assert sources_css.exists()
    assert '@import "./styles/sources.css";' in globals_css
    for selector in [
        "\n.sources-scroll {",
        "\n.sources-panel-head {",
        "\n.sources-ingest-button {",
        "\n.folder-card {",
        "\n.video-card {",
        "\n.video-player-modal {",
    ]:
        assert selector not in globals_css


def test_sources_styles_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    styles_dir = project_root / "frontend" / "app" / "styles"
    sources_css = (styles_dir / "sources.css").read_text(encoding="utf-8")

    expected_imports = [
        "./sources-panel-shell.css",
        "./sources-empty-state.css",
        "./sources-ingestion-controls.css",
        "./sources-folder-list.css",
        "./sources-video-cards.css",
        "./sources-player-modal.css",
        "./source-references.css",
        "./sources-theme-overrides.css",
        "./sources-responsive.css",
    ]
    expected_anchors = {
        "sources-panel-shell.css": ".panel-sources .panel-body {",
        "sources-empty-state.css": ".sources-empty-state {",
        "sources-ingestion-controls.css": ".sources-ingest-button {",
        "sources-folder-list.css": ".folder-card {",
        "sources-video-cards.css": ".video-card {",
        "sources-player-modal.css": ".video-player-modal {",
        "source-references.css": ".source-details {",
        "sources-theme-overrides.css": "html.light .folder-card.selected {",
        "sources-responsive.css": "@media (max-width: 1024px)",
    }

    for imported_path in expected_imports:
        imported_file = styles_dir / imported_path.removeprefix("./")
        assert imported_file.exists()
        assert expected_anchors[imported_file.name] in imported_file.read_text(
            encoding="utf-8"
        )
        assert f'@import "{imported_path}";' in sources_css

    for selector in [
        "\n.panel-sources .panel-body {",
        "\n.sources-empty-state {",
        "\n.sources-ingest-button {",
        "\n.folder-card {",
        "\n.video-card {",
        "\n.video-player-modal {",
        "\n.source-details {",
        "\nhtml.light .folder-card.selected {",
        "\n@media (max-width: 1024px)",
    ]:
        assert selector not in sources_css


def test_global_styles_delegate_knowledge_sidebar_styles_to_feature_file():
    project_root = Path(__file__).resolve().parents[1]
    globals_css = (project_root / "frontend" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )
    knowledge_css = (
        project_root / "frontend" / "app" / "styles" / "knowledge-sidebar.css"
    )

    assert knowledge_css.exists()
    assert '@import "./styles/knowledge-sidebar.css";' in globals_css
    for selector in [
        "\n.knowledge-panel {",
        "\n.knowledge-select-trigger {",
        "\n.knowledge-delete-card {",
        "\n.knowledge-create-card {",
        "\n.knowledge-active-hint {",
    ]:
        assert selector not in globals_css


def test_global_styles_delegate_chat_styles_to_feature_file():
    project_root = Path(__file__).resolve().parents[1]
    globals_css = (project_root / "frontend" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )
    chat_css = project_root / "frontend" / "app" / "styles" / "chat.css"

    assert chat_css.exists()
    assert '@import "./styles/chat.css";' in globals_css
    for selector in [
        "\n.progress {",
        "\n.code-block-wrap {",
        "\n.thinking-process {",
        "\n.message {",
        "\n.markdown {",
        "\n.web-search-live-status {",
        "\n.web-search-status {",
        "\n.message-actions {",
        "\n.empty-state {",
        "\n.prompt-grid {",
    ]:
        assert selector not in globals_css


def test_chat_styles_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    styles_dir = project_root / "frontend" / "app" / "styles"
    chat_css = (styles_dir / "chat.css").read_text(encoding="utf-8")

    expected_imports = [
        "./chat-progress.css",
        "./chat-messages.css",
        "./chat-markdown.css",
        "./chat-web-search.css",
        "./chat-message-actions.css",
        "./chat-empty-state.css",
        "./chat-responsive.css",
        "./chat-code-blocks.css",
        "./chat-thinking.css",
    ]
    expected_anchors = {
        "chat-progress.css": ".progress {",
        "chat-messages.css": ".message {",
        "chat-markdown.css": ".markdown {",
        "chat-web-search.css": ".web-search-live-status {",
        "chat-message-actions.css": ".message-actions {",
        "chat-empty-state.css": ".empty-state {",
        "chat-responsive.css": "@media (max-width: 1024px)",
        "chat-code-blocks.css": ".code-block-wrap {",
        "chat-thinking.css": ".thinking-process {",
    }

    for imported_path in expected_imports:
        imported_file = styles_dir / imported_path.removeprefix("./")
        assert imported_file.exists()
        assert expected_anchors[imported_file.name] in imported_file.read_text(
            encoding="utf-8"
        )
        assert f'@import "{imported_path}";' in chat_css

    for selector in [
        "\n.progress {",
        "\n.message {",
        "\n.markdown {",
        "\n.web-search-live-status {",
        "\n.message-actions {",
        "\n.empty-state {",
        "\n@media (max-width: 1024px)",
        "\n.code-block-wrap {",
        "\n.thinking-process {",
    ]:
        assert selector not in chat_css


def test_global_styles_delegate_chat_control_styles_to_feature_file():
    project_root = Path(__file__).resolve().parents[1]
    globals_css = (project_root / "frontend" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )
    controls_css = project_root / "frontend" / "app" / "styles" / "chat-controls.css"

    assert controls_css.exists()
    assert '@import "./styles/chat-controls.css";' in globals_css
    for selector in [
        "\n.composer-shell {",
        "\n.composer-input {",
        "\n.scope-picker {",
        "\n.scope-picker-trigger {",
        "\n.model-status-card {",
        "\n.model-provider-menu {",
        "\n.input {",
        "\n.btn {",
        "\n.status-pill {",
    ]:
        assert selector not in globals_css


def test_chat_control_styles_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    styles_dir = project_root / "frontend" / "app" / "styles"
    controls_css = (styles_dir / "chat-controls.css").read_text(encoding="utf-8")

    expected_imports = [
        "./chat-composer-controls.css",
        "./chat-scope-picker.css",
        "./chat-model-controls.css",
        "./control-primitives.css",
        "./chat-controls-responsive.css",
    ]
    expected_anchors = {
        "chat-composer-controls.css": ".composer-shell {",
        "chat-scope-picker.css": ".scope-picker {",
        "chat-model-controls.css": ".model-status-card {",
        "control-primitives.css": ".input {",
        "chat-controls-responsive.css": "@media (max-width: 1024px)",
    }

    for imported_path in expected_imports:
        imported_file = styles_dir / imported_path.removeprefix("./")
        assert imported_file.exists()
        assert expected_anchors[imported_file.name] in imported_file.read_text(
            encoding="utf-8"
        )
        assert f'@import "{imported_path}";' in controls_css

    for selector in [
        "\n.composer-shell {",
        "\n.scope-picker {",
        "\n.model-status-card {",
        "\n.input {",
        "\n.btn {",
        "\n@media (max-width: 1024px)",
    ]:
        assert selector not in controls_css


def test_global_styles_delegate_import_organize_styles_to_feature_file():
    project_root = Path(__file__).resolve().parents[1]
    globals_css = (project_root / "frontend" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )
    import_css = project_root / "frontend" / "app" / "styles" / "import-organize.css"

    assert import_css.exists()
    assert '@import "./styles/import-organize.css";' in globals_css
    for selector in [
        "\n.import-modal {",
        "\n.import-method-card {",
        "\n.import-local-video-card {",
        "\n.organize-modal {",
        "\n.organize-item {",
    ]:
        assert selector not in globals_css


def test_import_organize_styles_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    styles_dir = project_root / "frontend" / "app" / "styles"
    import_css = (styles_dir / "import-organize.css").read_text(encoding="utf-8")

    expected_imports = [
        "./import-methods.css",
        "./import-step-shell.css",
        "./import-qr.css",
        "./import-video.css",
        "./import-theme-overrides.css",
        "./organize-preview.css",
        "./import-organize-responsive.css",
    ]
    expected_anchors = {
        "import-methods.css": ".import-modal {",
        "import-step-shell.css": ".import-modal-step {",
        "import-qr.css": ".import-bound-card,",
        "import-video.css": ".import-url-label {",
        "import-theme-overrides.css": "html.light .import-back-btn {",
        "organize-preview.css": ".organize-modal {",
        "import-organize-responsive.css": "@media (max-width: 640px)",
    }

    for imported_path in expected_imports:
        imported_file = styles_dir / imported_path.removeprefix("./")
        assert imported_file.exists()
        assert expected_anchors[imported_file.name] in imported_file.read_text(
            encoding="utf-8"
        )
        assert f'@import "{imported_path}";' in import_css

    for selector in [
        "\n.import-modal {",
        "\n.import-modal-step {",
        "\n.import-bound-card,",
        "\n.import-url-label {",
        "\nhtml.light .import-back-btn {",
        "\n.organize-modal {",
        "\n@media (max-width: 640px)",
    ]:
        assert selector not in import_css


def test_global_styles_delegate_residual_feature_styles_to_feature_files():
    project_root = Path(__file__).resolve().parents[1]
    globals_css = (project_root / "frontend" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )
    demo_css = project_root / "frontend" / "app" / "styles" / "demo.css"

    assert demo_css.exists()
    assert '@import "./styles/demo.css";' in globals_css
    for selector in [
        "\n.user-message-actions {",
        "\n.empty-hero {",
        "\n.empty-hero-title {",
        "\n.empty-hero-copy {",
        "\n.kb-subtle-stat {",
        "\n.glass-action-btn {",
        "\n.demo-modal {",
        "\n.demo-grid {",
        "\n.demo-preview {",
        "\n.demo-sources {",
        "\n.demo-answer {",
        "\n.demo-actions {",
        "\n@keyframes fadeUp",
    ]:
        assert selector not in globals_css
