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
