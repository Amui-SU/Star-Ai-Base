from .helpers import get_project_root


def test_video_note_workspace_is_owned_by_page_not_entry_panels():
    project_root = get_project_root()
    page_source = (project_root / "frontend/app/page.tsx").read_text(
        encoding="utf-8"
    )
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
    style_path = project_root / "frontend/app/styles/video-notes.css"

    assert '@import "./styles/video-notes.css";' in globals_source
    assert style_path.exists()
    assert ".video-note-workspace" in style_path.read_text(encoding="utf-8")
