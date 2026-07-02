from tests.service_boundaries.helpers import function_source
from tests.service_boundaries.helpers import get_project_root


def test_knowledge_base_router_delegates_status_search_delete_runtime_to_service():
    project_root = get_project_root()
    router_path = project_root / "app/routers/knowledge_bases.py"
    runtime_path = project_root / "app/services/knowledge_base_route_runtime.py"

    assert runtime_path.exists()
    router_source = router_path.read_text(encoding="utf-8")
    runtime_source = runtime_path.read_text(encoding="utf-8")

    assert "async def get_knowledge_base_build_status_from_router" in runtime_source
    assert "async def search_knowledge_base_from_router" in runtime_source
    assert "async def delete_knowledge_base_from_router" in runtime_source
    assert "from app.services.knowledge_base_route_runtime import" in router_source

    assert "get_build_status_payload" not in router_source
    assert "from app.services.knowledge_base_search import" not in router_source
    assert "from app.services.knowledge_base_delete import" not in router_source

    status_route_source = function_source(router_source, "get_build_status")
    assert "get_knowledge_base_build_status_from_router(" in status_route_source
    assert "get_build_status_payload(" not in status_route_source

    search_route_source = function_source(router_source, "search_knowledge_base")
    assert "search_knowledge_base_from_router(" in search_route_source
    assert "search_knowledge_base_documents(" not in search_route_source
    assert "rag_service_factory=get_rag_service" in search_route_source

    delete_route_source = function_source(router_source, "delete_knowledge_base")
    assert "delete_knowledge_base_from_router(" in delete_route_source
    assert "delete_knowledge_base_service(" not in delete_route_source
    assert "rag_service_factory=get_rag_service" in delete_route_source
    assert "supports_keyword_argument_func=_supports_keyword_argument" in (
        delete_route_source
    )
