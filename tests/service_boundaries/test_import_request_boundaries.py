from tests.service_boundaries.helpers import function_source
from tests.service_boundaries.helpers import get_project_root


def test_import_router_delegates_request_runtime_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/import_request_runtime.py"
    router_source = (project_root / "app/routers/imports.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in {
        "detect_import_source_type",
        "extract_bilibili_bvid",
        "prepare_bilibili_import_request",
        "prepare_local_video_import_request",
    }:
        assert f"def {name}" in service_source or f"async def {name}" in service_source

    assert "from app.services.import_request_runtime import" in router_source
    assert "import re" not in router_source
    assert "import shutil" not in router_source
    assert "import uuid" not in router_source
    assert "from urllib.parse import urlparse" not in router_source
    assert "KnowledgeBase" not in router_source

    import_url_source = function_source(router_source, "import_url")
    import_local_source = function_source(router_source, "import_local_video")

    assert "_detect_source_type(" not in import_url_source
    assert "_extract_bvid(" not in import_url_source
    assert "_get_owned_knowledge_base(" not in import_url_source
    assert "create_ingestion_task(" not in import_url_source
    assert "background_tasks.add_task(" not in import_url_source

    assert "_is_video_upload(" not in import_local_source
    assert "_get_owned_knowledge_base(" not in import_local_source
    assert "_local_video_id(" not in import_local_source
    assert "_safe_upload_suffix(" not in import_local_source
    assert "shutil.copyfileobj(" not in import_local_source
    assert "create_ingestion_task(" not in import_local_source
    assert "background_tasks.add_task(" not in import_local_source
