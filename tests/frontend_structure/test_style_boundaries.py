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


def test_chat_styles_delegate_to_focused_files():
    project_root = get_project_root()
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


def test_chat_control_styles_delegate_to_focused_files():
    project_root = get_project_root()
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


def test_import_organize_styles_delegate_to_focused_files():
    project_root = get_project_root()
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
