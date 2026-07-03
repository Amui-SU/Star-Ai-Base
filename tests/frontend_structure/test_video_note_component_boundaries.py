import re

from .helpers import get_project_root


VIDEO_NOTE_STYLE_FILES = [
    "video-notes/shell.css",
    "video-notes/list.css",
    "video-notes/tool-rail-export.css",
    "video-notes/editor.css",
    "video-notes/side-panels.css",
    "video-notes/responsive.css",
]


def _video_note_style_source(project_root) -> str:
    style_dir = project_root / "frontend/app/styles"
    hub_path = style_dir / "video-notes.css"
    sources = [hub_path.read_text(encoding="utf-8")]
    for relative_path in VIDEO_NOTE_STYLE_FILES:
        path = style_dir / relative_path
        assert path.exists()
        sources.append(path.read_text(encoding="utf-8"))
    return "\n".join(sources)


def test_video_note_workspace_is_owned_by_page_not_entry_panels():
    project_root = get_project_root()
    page_source = (project_root / "frontend/app/page.tsx").read_text(encoding="utf-8")
    chat_panel = (project_root / "frontend/components/ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    sources_panel = (project_root / "frontend/components/SourcesPanel.tsx").read_text(
        encoding="utf-8"
    )

    assert "VideoNoteWorkspace" in page_source
    assert "VideoNoteWorkspace" not in chat_panel
    assert "VideoNoteWorkspace" not in sources_panel
    assert "videoNoteApi" not in chat_panel
    assert "videoNoteApi" not in sources_panel


def test_video_note_feature_styles_stay_in_dedicated_file():
    project_root = get_project_root()
    globals_source = (project_root / "frontend/app/globals.css").read_text(
        encoding="utf-8"
    )
    style_dir = project_root / "frontend/app/styles"
    style_path = project_root / "frontend/app/styles/video-notes.css"

    assert '@import "./styles/video-notes.css";' in globals_source
    assert style_path.exists()
    hub_source = style_path.read_text(encoding="utf-8")
    for relative_path in VIDEO_NOTE_STYLE_FILES:
        assert f'@import "./{relative_path}";' in hub_source
        assert (style_dir / relative_path).exists()
    assert ".video-note-workspace" in _video_note_style_source(project_root)


def test_video_note_styles_are_split_by_surface():
    project_root = get_project_root()
    style_dir = project_root / "frontend/app/styles"
    expected_tokens = {
        "video-notes/shell.css": [
            ".video-note-drawer",
            ".video-note-workspace",
            ".video-note-header",
        ],
        "video-notes/list.css": [
            ".video-note-list-search",
            ".video-note-list-item",
            ".video-note-current-badge",
        ],
        "video-notes/tool-rail-export.css": [
            ".video-note-tool-rail",
            ".video-note-export-menu",
            ".video-note-export-popover",
        ],
        "video-notes/editor.css": [
            ".video-note-markdown-editor",
            ".video-note-vditor",
            ".video-note-template-grid",
        ],
        "video-notes/side-panels.css": [
            ".video-note-ai-panel",
            ".video-note-ai-expand",
            ".video-note-export-result",
        ],
        "video-notes/responsive.css": [
            "@media (max-width: 1024px)",
            "@media (max-width: 640px)",
            ".video-note-workspace .video-note-list-panel[hidden]",
        ],
    }

    hub_source = (style_dir / "video-notes.css").read_text(encoding="utf-8")
    assert hub_source.count("@import") == len(expected_tokens)
    assert len(hub_source.splitlines()) <= 12

    for relative_path, tokens in expected_tokens.items():
        source = (style_dir / relative_path).read_text(encoding="utf-8")
        assert len(source.splitlines()) <= 320
        for token in tokens:
            assert token in source


def test_video_note_workspace_tests_are_split_by_workflow():
    project_root = get_project_root()
    test_dir = project_root / "frontend/components/video-notes"
    expected_files = {
        "VideoNoteWorkspace.selection.test.tsx": [
            "opens directly into the first existing note",
            "opens selectable videos in a chooser menu",
            "loads the list and creates a standard template note",
        ],
        "VideoNoteWorkspace.export.test.tsx": [
            "autosaves copied Markdown from the toolbar menu",
            "downloads exported Markdown from the toolbar export menu",
        ],
        "VideoNoteWorkspace.ai.test.tsx": [
            "collapses and restores the right AI tools",
            "applies AI suggestions with status",
        ],
    }
    helper_path = test_dir / "VideoNoteWorkspace.test-utils.tsx"
    original_path = test_dir / "VideoNoteWorkspace.test.tsx"

    assert helper_path.exists()
    helper_source = helper_path.read_text(encoding="utf-8")
    assert 'vi.mock("@/lib/api"' in helper_source
    assert 'vi.mock("vditor"' in helper_source
    assert "function findMarkdownEditor" in helper_source

    focused_source = ""
    for file_name, expected_names in expected_files.items():
        path = test_dir / file_name
        assert path.exists()
        source = path.read_text(encoding="utf-8")
        focused_source += source
        for expected_name in expected_names:
            assert expected_name in source

    assert not original_path.exists()
    assert focused_source.count("it(") == 7


def test_video_note_workspace_uses_focused_view_component():
    project_root = get_project_root()
    component_dir = project_root / "frontend/components/video-notes"
    workspace_path = component_dir / "VideoNoteWorkspace.tsx"
    view_path = component_dir / "VideoNoteWorkspaceView.tsx"

    assert view_path.exists()

    workspace_source = workspace_path.read_text(encoding="utf-8")
    view_source = view_path.read_text(encoding="utf-8")

    assert 'import VideoNoteWorkspaceView from "./VideoNoteWorkspaceView";' in (
        workspace_source
    )
    assert "<VideoNoteWorkspaceView" in workspace_source
    for token in [
        "VideoNoteHeader",
        "VideoNoteListPanel",
        "VideoNoteMarkdownEditor",
        "VideoNoteAiPanel",
        "VideoNoteTemplatePicker",
        "VideoNoteToolRail",
        "video-note-workspace",
        "video-note-chooser-menu",
        "video-note-side-panel",
    ]:
        assert token not in workspace_source
        assert token in view_source


def test_video_note_mobile_drawer_collapses_to_single_column_layout():
    project_root = get_project_root()
    css = _video_note_style_source(project_root)

    mobile_css = css.split("@media (max-width: 1024px)", maxsplit=1)[1]

    assert ".video-note-workspace.drawer.chooser-collapsed" in mobile_css
    assert "grid-template-columns: minmax(0, 1fr);" in mobile_css
    assert (
        ".video-note-workspace.drawer.chooser-collapsed .video-note-main" in mobile_css
    )
    assert (
        ".video-note-workspace.drawer.chooser-collapsed .video-note-side-panel"
        in mobile_css
    )


def test_video_note_menu_polish_styles_guard_overlay_and_scroll_layout():
    project_root = get_project_root()
    css = _video_note_style_source(project_root)
    mobile_css = css.split("@media (max-width: 1024px)", maxsplit=1)[1]

    assert ".video-note-chooser-menu" in css
    assert ".video-note-export-menu" in css
    assert ".video-note-workspace.ai-collapsed" in css
    assert ".video-note-vditor .vditor-ir" in css
    assert ".video-note-vditor .vditor-ir .vditor-reset" in css
    assert "overflow: auto;" in css
    assert ".video-note-chooser-menu" in mobile_css
    assert "position: fixed;" in mobile_css
    assert "inset: 0;" in mobile_css
    assert ".video-note-workspace .video-note-chooser-menu {" in mobile_css
    assert (
        ".video-note-workspace .video-note-chooser-menu .video-note-list-panel"
        in mobile_css
    )
    assert "height: 100dvh;" in mobile_css


def test_video_note_export_menu_styles_keep_actions_readable():
    project_root = get_project_root()
    css = _video_note_style_source(project_root)
    action_override = re.search(
        r"\.video-note-tool-rail \.video-note-export-action\s*\{(?P<body>[^}]+)\}",
        css,
    )

    assert action_override is not None
    action_body = action_override.group("body")
    assert "grid-template-columns: 18px minmax(0, 1fr);" in action_body
    assert "padding: 0 12px;" in action_body
    assert ".video-note-export-field" in css
    assert ".video-note-export-template-input" in css


def test_video_note_editor_polish_styles_guard_tooltips_and_blocks():
    project_root = get_project_root()
    css = _video_note_style_source(project_root)

    assert ".video-note-vditor .vditor-tooltipped::after" in css
    assert ".video-note-vditor .vditor-toolbar .vditor-tooltipped::after" in css
    assert "top: calc(100% + 8px);" in css
    assert ".video-note-markdown-editor" in css
    assert "overflow: visible;" in css
    assert ".video-note-vditor .vditor-ir p" in css
    assert '.video-note-vditor .vditor-ir input[type="checkbox"]' in css
    assert ".video-note-side-panel.collapsed" in css
