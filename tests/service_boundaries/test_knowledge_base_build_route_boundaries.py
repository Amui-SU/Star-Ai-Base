from tests.service_boundaries.helpers import function_source
from tests.service_boundaries.helpers import get_project_root


def test_knowledge_base_router_delegates_build_route_runtime_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_build_route_runtime.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def start_knowledge_base_build" in service_source
    assert (
        "from app.services.knowledge_base_build_route_runtime import" in router_source
    )

    build_route_source = function_source(router_source, "build_knowledge_base")
    assert "start_knowledge_base_build(" in build_route_source
    assert "prepare_knowledge_base_build_request(" not in build_route_source
    assert "background_tasks.add_task(" not in build_route_source
    assert "resolve_build_rag_service(" not in build_route_source
    assert "_get_rag_service_for_build(" not in build_route_source

    assert "from app.services.knowledge_base_build_requests import" not in router_source
    assert "from app.services.knowledge_base_build_runtime import" not in router_source
    assert "def _get_rag_service_for_build" not in router_source
