from .helpers import get_project_root


def test_workspace_styles_delegate_to_focused_files():
    project_root = get_project_root()
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


def test_account_panel_styles_delegate_to_focused_files():
    project_root = get_project_root()
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


def test_sources_styles_delegate_to_focused_files():
    project_root = get_project_root()
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


def test_knowledge_sidebar_styles_delegate_to_focused_files():
    project_root = get_project_root()
    styles_dir = project_root / "frontend" / "app" / "styles"
    knowledge_css = (styles_dir / "knowledge-sidebar.css").read_text(encoding="utf-8")

    expected_imports = [
        "./knowledge-panel-shell.css",
        "./knowledge-selector.css",
        "./knowledge-delete.css",
        "./knowledge-theme-overrides.css",
        "./knowledge-create.css",
        "./knowledge-responsive.css",
    ]
    expected_anchors = {
        "knowledge-panel-shell.css": ".knowledge-panel {",
        "knowledge-selector.css": ".knowledge-select {",
        "knowledge-delete.css": ".knowledge-delete-icon {",
        "knowledge-theme-overrides.css": "html.light .knowledge-select-trigger {",
        "knowledge-create.css": ".knowledge-create-card {",
        "knowledge-responsive.css": "@media (max-width: 640px)",
    }

    for imported_path in expected_imports:
        imported_file = styles_dir / imported_path.removeprefix("./")
        assert imported_file.exists()
        assert expected_anchors[imported_file.name] in imported_file.read_text(
            encoding="utf-8"
        )
        assert f'@import "{imported_path}";' in knowledge_css

    for selector in [
        "\n.knowledge-panel {",
        "\n.knowledge-select {",
        "\n.knowledge-delete-icon {",
        "\nhtml.light .knowledge-select-trigger {",
        "\n.knowledge-create-card {",
        "\n@media (max-width: 640px)",
    ]:
        assert selector not in knowledge_css
