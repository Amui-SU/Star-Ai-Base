from .helpers import get_project_root


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


def test_auth_page_presentation_components_are_extracted():
    project_root = get_project_root()
    auth_page = (project_root / "frontend" / "components" / "AuthPage.tsx").read_text(
        encoding="utf-8"
    )

    assert (project_root / "frontend/components/auth/AuthCard.tsx").exists()
    assert (project_root / "frontend/components/auth/AuthOAuthButtons.tsx").exists()
    assert "@/components/auth/AuthCard" in auth_page
    assert "@/components/auth/AuthOAuthButtons" not in auth_page
    assert "renderOAuthIcon" not in auth_page
    assert "auth-oauth-grid" not in auth_page
    assert "handleRegister" not in auth_page
    assert "handleSendCode" not in auth_page
    assert "auth-code-row" not in auth_page


def test_auth_card_presentation_boundaries_are_extracted():
    project_root = get_project_root()
    auth_card = (
        project_root / "frontend" / "components" / "auth" / "AuthCard.tsx"
    ).read_text(encoding="utf-8")

    assert (project_root / "frontend/components/auth/authCardStyles.ts").exists()
    assert (project_root / "frontend/components/auth/AuthCardParts.tsx").exists()
    assert (project_root / "frontend/components/auth/AuthCardSteps.tsx").exists()
    assert "@/components/auth/authCardStyles" in auth_card
    assert "@/components/auth/AuthCardSteps" in auth_card
    assert "CSSProperties" not in auth_card
    assert "AuthOAuthButtons" not in auth_card
    assert "const inputStyle" not in auth_card
    assert "const authCardStyle" not in auth_card
    assert "function AuthError" not in auth_card
    assert "function AuthSeparator" not in auth_card
    assert "auth-code-row" not in auth_card


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
    footer = (
        project_root / "frontend" / "components" / "sources" / "SourcesPanelFooter.tsx"
    ).read_text(encoding="utf-8")

    assert (project_root / "frontend/components/sources/sourcesPanelLogic.ts").exists()
    assert "@/components/sources/sourcesPanelLogic" in footer
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


def test_sources_panel_folder_list_is_extracted():
    project_root = get_project_root()
    sources_panel = (
        project_root / "frontend" / "components" / "SourcesPanel.tsx"
    ).read_text(encoding="utf-8")
    folder_list = (
        project_root / "frontend" / "components" / "sources" / "SourcesFolderList.tsx"
    )

    assert folder_list.exists()
    assert "@/components/sources/SourcesFolderList" in sources_panel
    assert "folder-card" not in sources_panel
    assert "folder-list-wrapper" not in sources_panel
    assert "video-card" not in sources_panel
    assert "video-title-input" not in sources_panel


def test_sources_panel_sections_and_selection_are_extracted():
    project_root = get_project_root()
    sources_panel = (
        project_root / "frontend" / "components" / "SourcesPanel.tsx"
    ).read_text(encoding="utf-8")

    assert (
        project_root / "frontend/components/sources/useSourcesSelection.ts"
    ).exists()
    assert (
        project_root / "frontend/components/sources/SourcesPanelHeader.tsx"
    ).exists()
    assert (project_root / "frontend/components/sources/SourcesEmptyState.tsx").exists()
    assert (
        project_root / "frontend/components/sources/SourcesPanelFooter.tsx"
    ).exists()
    assert "@/components/sources/useSourcesSelection" in sources_panel
    assert "@/components/sources/SourcesPanelHeader" in sources_panel
    assert "@/components/sources/SourcesEmptyState" in sources_panel
    assert "@/components/sources/SourcesPanelFooter" in sources_panel
    assert "const [selected" not in sources_panel
    assert "const toggleSelect" not in sources_panel
    assert "const toggleVideoSelect" not in sources_panel
    assert "sources-empty-state" not in sources_panel
    assert "panel-footer" not in sources_panel
    assert "默认收藏夹" not in sources_panel
    assert "getSourcesBuildButtonText" not in sources_panel


def test_workspace_state_is_extracted_from_home_page():
    project_root = get_project_root()
    page = (project_root / "frontend" / "app" / "page.tsx").read_text(encoding="utf-8")

    assert (project_root / "frontend/app/useWorkspaceState.ts").exists()
    assert "@/app/useWorkspaceState" in page
    assert "const getInitialSidebarOpen" not in page
    assert "const isMobileViewport" not in page
    assert 'localStorage.getItem("sidebar_width")' not in page


def test_home_page_shell_state_is_extracted():
    project_root = get_project_root()
    page = (project_root / "frontend" / "app" / "page.tsx").read_text(encoding="utf-8")

    assert (project_root / "frontend/app/useHomePageShell.ts").exists()
    assert "@/app/useHomePageShell" in page
    assert "systemAuthApi" not in page
    assert "sourceBindingApi" not in page
    assert 'localStorage.getItem("active_kb_id")' not in page
    assert 'localStorage.setItem("active_kb_id"' not in page
    assert 'localStorage.removeItem("active_kb_id")' not in page
