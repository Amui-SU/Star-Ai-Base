from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import get_project_root


def test_chat_router_delegates_video_context_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/chat_video_context.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(chat_source)

    expected_service_names = {
        "is_related_to_collection",
        "get_folder_ids_for_session",
        "get_bvids_by_folder_ids",
        "get_video_context",
        "get_video_titles_context",
    }
    router_private_names = {
        "_is_related_to_collection",
        "_get_folder_ids_for_session",
        "_get_bvids_by_folder_ids",
        "_get_video_context",
        "_get_video_titles_context",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"async def {name}" in service_source
    assert "from app.services.chat_video_context import" in chat_source
    assert "VideoCache.description.ilike" not in chat_source
    assert "FavoriteFolder.updated_at.desc()" not in chat_source
    assert "FavoriteVideo.folder_id == FavoriteFolder.id" not in chat_source
    assert declared_names.isdisjoint(router_private_names)


def test_chat_router_delegates_message_preparation_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/chat_message_preparation.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def prepare_chat_messages" in service_source
    assert "from app.services.chat_message_preparation import" in chat_source
    assert "rag.search(question, k=5" not in chat_source
    assert "route, route_raw = _route_with_llm(" not in chat_source
    assert "context_parts, sources, seen_bvids = [], [], set()" not in chat_source


def test_chat_router_delegates_legacy_ask_runtime_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/chat_runtime.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")

    ask_route_source = chat_source[
        chat_source.index("async def ask_question(") : chat_source.index(
            '@router.post("/ask/stream")'
        )
    ]
    stream_route_source = chat_source[
        chat_source.index("async def ask_question_stream(") : chat_source.index(
            '@router.post("/search")'
        )
    ]

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def answer_legacy_chat" in service_source
    assert "async def stream_legacy_chat" in service_source
    assert "from app.services.chat_runtime import" in chat_source

    assert "answer_legacy_chat(" in ask_route_source
    assert "_resolve_llm_config(" not in ask_route_source
    assert "_prepare_messages(" not in ask_route_source
    assert "_get_llm_client(" not in ask_route_source
    assert "client.chat.completions.create(" not in ask_route_source
    assert "ChatResponse(" not in ask_route_source

    assert "stream_legacy_chat(" in stream_route_source
    assert "def generate" not in stream_route_source
    assert "_stream_llm_events(" not in stream_route_source
    assert "_encode_thinking_delta(" not in stream_route_source
    assert "json.dumps(" not in stream_route_source
