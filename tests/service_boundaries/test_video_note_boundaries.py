from .helpers import declared_callable_names
from .helpers import get_project_root


def test_video_note_router_delegates_to_route_runtime():
    project_root = get_project_root()
    router_path = project_root / "app/routers/video_notes.py"
    runtime_path = project_root / "app/services/video_note_route_runtime.py"

    assert router_path.exists()
    assert runtime_path.exists()

    router_source = router_path.read_text(encoding="utf-8")
    router_callables = declared_callable_names(router_source)

    assert "from app.services.video_note_route_runtime import" in router_source
    assert "select(" not in router_source
    assert ".execute(" not in router_source
    assert "VideoNote(" not in router_source
    assert len(router_callables) <= 8


def test_video_note_domain_has_focused_service_modules():
    project_root = get_project_root()

    expected = {
        "app/services/video_note_presenters.py": [
            "resolve_video_note_source",
            "build_standard_note_blocks",
        ],
        "app/services/video_note_markdown.py": [
            "render_video_note_markdown",
            "render_video_note_filename",
        ],
        "app/services/video_note_ai.py": [
            "build_summary_suggestions",
            "build_ai_edit_suggestions",
        ],
    }

    for relative_path, symbols in expected.items():
        path = project_root / relative_path
        assert path.exists()
        source = path.read_text(encoding="utf-8")
        for symbol in symbols:
            assert f"def {symbol}" in source or f"async def {symbol}" in source


def test_chat_and_sources_do_not_own_video_note_runtime():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend/components/ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    sources_panel = (project_root / "frontend/components/SourcesPanel.tsx").read_text(
        encoding="utf-8"
    )

    forbidden_tokens = {
        "videoNoteApi",
        "VideoNoteWorkspace",
        "useVideoNoteAutosave",
        "useVideoNoteAiEditing",
    }

    for token in forbidden_tokens:
        assert token not in chat_panel
        assert token not in sources_panel
