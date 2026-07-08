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
        "app/services/video_note_route_query_runtime.py": [
            "list_video_notes_from_router",
            "get_video_note_detail_from_router",
        ],
        "app/services/video_note_route_mutation_runtime.py": [
            "create_video_note_from_router",
            "update_video_note_from_router",
        ],
        "app/services/video_note_route_export_runtime.py": [
            "export_video_note_markdown_from_router",
        ],
        "app/services/video_note_route_ai_runtime.py": [
            "generate_video_note_summary_from_router",
            "edit_video_note_with_ai_from_router",
        ],
        "app/services/video_note_presenters.py": [
            "resolve_video_note_source",
            "build_standard_note_blocks",
        ],
        "app/services/video_note_markdown.py": [
            "render_video_note_markdown",
            "render_video_note_filename",
        ],
        "app/services/video_note_ai.py": [
            "build_summary_messages",
            "generate_video_note_ai_json",
        ],
        "app/services/video_note_ai_suggestions.py": [
            "build_summary_suggestions",
            "build_ai_edit_suggestions",
        ],
        "app/services/video_note_chapters.py": [
            "extract_bilibili_view_point_timestamps",
            "fetch_bilibili_view_point_timestamps",
        ],
    }

    for relative_path, symbols in expected.items():
        path = project_root / relative_path
        assert path.exists()
        source = path.read_text(encoding="utf-8")
        for symbol in symbols:
            assert f"def {symbol}" in source or f"async def {symbol}" in source


def test_video_note_route_runtime_stays_a_facade():
    project_root = get_project_root()
    runtime_path = project_root / "app/services/video_note_route_runtime.py"
    runtime_source = runtime_path.read_text(encoding="utf-8")
    runtime_callables = declared_callable_names(runtime_source)

    assert "from app.services.video_note_route_query_runtime import" in runtime_source
    assert (
        "from app.services.video_note_route_mutation_runtime import" in runtime_source
    )
    assert "from app.services.video_note_route_export_runtime import" in runtime_source
    assert "from app.services.video_note_route_ai_runtime import" in runtime_source
    assert runtime_callables == set()

    misplaced_tokens = {
        "select(",
        "VideoNote(",
        "resolve_user_llm_credentials",
        "generate_video_note_ai_json",
        "render_video_note_markdown",
        "build_standard_note_blocks",
        "_normalized_tags",
    }
    for token in misplaced_tokens:
        assert token not in runtime_source


def test_video_note_ai_suggestions_stay_out_of_prompt_runtime():
    project_root = get_project_root()
    ai_path = project_root / "app/services/video_note_ai.py"
    suggestions_path = project_root / "app/services/video_note_ai_suggestions.py"

    assert suggestions_path.exists()

    ai_source = ai_path.read_text(encoding="utf-8")
    suggestions_source = suggestions_path.read_text(encoding="utf-8")

    assert "from app.services.video_note_ai_suggestions import" in ai_source
    assert "def build_summary_suggestions" not in ai_source
    assert "def build_ai_edit_suggestions" not in ai_source
    assert "def _payload_strings" not in ai_source
    assert "def _payload_timestamps" not in ai_source
    assert "def build_summary_suggestions" in suggestions_source
    assert "def build_ai_edit_suggestions" in suggestions_source


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
