from .helpers import get_project_root


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
