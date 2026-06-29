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
