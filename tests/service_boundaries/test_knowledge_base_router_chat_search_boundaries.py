from tests.service_boundaries.helpers import function_source
from tests.service_boundaries.helpers import get_project_root


def test_knowledge_base_router_delegates_search_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_search.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def search_knowledge_base_documents" in service_source
    assert "from app.services.knowledge_base_search import" in router_source
    assert 'detail="Search query cannot be empty"' not in router_source
    assert "rag.search_in_knowledge_base(" not in router_source
    assert "KnowledgeBaseSearchResponse(" not in router_source


def test_knowledge_base_router_delegates_non_streaming_chat_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_chat.py"
    runtime_path = project_root / "app/services/knowledge_base_chat_runtime.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    chat_route_source = function_source(router_source, "chat_with_knowledge_base")

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def answer_knowledge_base_chat" in service_source
    assert runtime_path.exists()
    runtime_source = runtime_path.read_text(encoding="utf-8")
    assert "async def answer_knowledge_base_chat_from_router" in runtime_source
    assert "from app.services.knowledge_base_chat import" in runtime_source
    assert "from app.services.knowledge_base_chat_runtime import" in router_source
    assert "from app.services.knowledge_base_chat import" not in router_source
    assert "answer_knowledge_base_chat_from_router(" in chat_route_source
    assert "answer_knowledge_base_chat(" not in chat_route_source
    assert "load_documents=" not in chat_route_source
    assert "complete_answer=" not in chat_route_source
    assert "record_usage=" not in chat_route_source
    assert "_load_scoped_chat_documents(" not in chat_route_source
    assert "resolve_user_llm_credentials(" not in chat_route_source
    assert "_complete_knowledge_base_answer(" not in chat_route_source
    assert "record_usage_event(" not in chat_route_source
    assert "ChatResponse(" not in chat_route_source


def test_knowledge_base_router_delegates_streaming_chat_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_chat_stream.py"
    runtime_path = project_root / "app/services/knowledge_base_chat_runtime.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    stream_route_source = function_source(
        router_source, "stream_chat_with_knowledge_base"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "def stream_knowledge_base_chat" in service_source
    assert runtime_path.exists()
    runtime_source = runtime_path.read_text(encoding="utf-8")
    assert "async def stream_knowledge_base_chat_from_router" in runtime_source
    assert "from app.services.knowledge_base_chat_stream import" in runtime_source
    assert "from app.services.knowledge_base_chat_runtime import" in router_source
    assert "from app.services.knowledge_base_chat_stream import" not in router_source
    assert "stream_knowledge_base_chat_from_router(" in stream_route_source
    assert "stream_knowledge_base_chat(" not in stream_route_source
    assert "load_documents=" not in stream_route_source
    assert "prepare_web_search_with_heartbeats=" not in stream_route_source
    assert "stream_llm_events=" not in stream_route_source
    assert "record_usage=" not in stream_route_source
    assert "async def generate" not in stream_route_source
    assert "_load_scoped_chat_documents(" not in stream_route_source
    assert "resolve_user_llm_credentials(" not in stream_route_source
    assert "_stream_llm_events(" not in stream_route_source
    assert "record_usage_event(" not in stream_route_source
    assert "json.dumps(" not in stream_route_source
