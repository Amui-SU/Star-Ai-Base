from tests.service_boundaries.helpers import function_source
from tests.service_boundaries.helpers import get_project_root


def test_knowledge_base_router_delegates_record_deletion_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_delete.py"
    runtime_path = project_root / "app/services/knowledge_base_route_runtime.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def delete_knowledge_base_records" in service_source
    assert "async def delete_knowledge_base" in service_source
    assert runtime_path.exists()
    runtime_source = runtime_path.read_text(encoding="utf-8")
    assert "from app.services.knowledge_base_delete import" in runtime_source
    assert "from app.services.knowledge_base_delete import" not in router_source
    assert "from app.services.knowledge_base_route_runtime import" in router_source
    delete_route_source = function_source(router_source, "delete_knowledge_base")
    assert "delete_knowledge_base_from_router(" in delete_route_source
    assert "delete_knowledge_base_service(" not in delete_route_source
    assert "delete_knowledge_base_records(" not in delete_route_source
    assert "delete_by_knowledge_base(" not in delete_route_source
    assert "await db.commit()" not in delete_route_source
    assert "VideoCache.__table__.delete" not in router_source
    assert "FavoriteFolder.__table__.delete" not in router_source
    assert "FavoriteVideo.__table__.delete" not in router_source
    assert "IngestionTask.__table__.delete" not in router_source
    assert "VideoTitleOverride.__table__.delete" not in router_source
