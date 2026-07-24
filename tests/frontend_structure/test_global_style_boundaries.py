from .helpers import get_project_root


def test_global_styles_delegate_auth_styles_to_feature_file():
    project_root = get_project_root()
    globals_css = (project_root / "frontend" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )
    auth_css = project_root / "frontend" / "app" / "styles" / "auth.css"

    assert auth_css.exists()
    assert '@import "./styles/auth.css";' in globals_css
    assert "html.auth-page-active" not in globals_css
    assert ".auth-page" not in globals_css


def test_global_styles_delegate_modal_shell_styles_to_feature_file():
    project_root = get_project_root()
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


def test_modal_styles_delegate_to_focused_files():
    project_root = get_project_root()
    styles_dir = project_root / "frontend" / "app" / "styles"
    modals_css = (styles_dir / "modals.css").read_text(encoding="utf-8")

    expected_imports = [
        "./modal-provider-config.css",
        "./modal-shell.css",
        "./modal-responsive.css",
    ]
    expected_anchors = {
        "modal-provider-config.css": ".thinking-provider-modal {",
        "modal-shell.css": ".modal-backdrop {",
        "modal-responsive.css": "@media (max-width: 1024px)",
    }

    for imported_path in expected_imports:
        imported_file = styles_dir / imported_path.removeprefix("./")
        assert imported_file.exists()
        assert expected_anchors[imported_file.name] in imported_file.read_text(
            encoding="utf-8"
        )
        assert f'@import "{imported_path}";' in modals_css

    for selector in [
        "\n.thinking-provider-modal {",
        "\n.modal-backdrop {",
        "\n@media (max-width: 1024px)",
    ]:
        assert selector not in modals_css


def test_global_styles_delegate_workspace_styles_to_feature_file():
    project_root = get_project_root()
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
    project_root = get_project_root()
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

    workspace_css = project_root / "frontend/app/styles/api-account-workspace.css"
    assert workspace_css.exists()
    assert '@import "./api-account-workspace.css";' in account_css.read_text(encoding="utf-8")


def test_global_styles_delegate_sources_styles_to_feature_file():
    project_root = get_project_root()
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
    project_root = get_project_root()
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
    project_root = get_project_root()
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
    project_root = get_project_root()
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
    project_root = get_project_root()
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
    project_root = get_project_root()
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
