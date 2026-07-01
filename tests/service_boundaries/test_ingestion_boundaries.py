from tests.service_boundaries.helpers import get_project_root


def test_ingestion_task_persistence_and_status_mapping_live_in_service():
    project_root = get_project_root()
    service_source = (project_root / "app/services/ingestion_tasks.py").read_text(
        encoding="utf-8"
    )
    imports_source = (project_root / "app/routers/imports.py").read_text(
        encoding="utf-8"
    )
    import_tasks_source = (project_root / "app/services/import_tasks.py").read_text(
        encoding="utf-8"
    )
    build_tasks_source = (
        project_root / "app/services/knowledge_base_build_tasks.py"
    ).read_text(encoding="utf-8")
    build_requests_source = (
        project_root / "app/services/knowledge_base_build_requests.py"
    ).read_text(encoding="utf-8")
    knowledge_bases_source = (
        project_root / "app/routers/knowledge_bases.py"
    ).read_text(encoding="utf-8")

    assert "def build_status_payload" in service_source
    assert "async def create_ingestion_task" in service_source
    assert "async def update_ingestion_task" in service_source
    assert "from app.services.ingestion_tasks import" in imports_source
    assert "from app.services.ingestion_tasks import" in build_requests_source
    assert "async def _create_import_task" not in imports_source
    assert "async def _update_import_task" not in imports_source
    assert "async def _update_task" not in knowledge_bases_source
    assert "update_ingestion_task" in import_tasks_source
    assert "create_ingestion_task(" in build_requests_source
    assert "create_ingestion_task(" not in knowledge_bases_source
    assert "update_task: TaskUpdater = update_ingestion_task" in build_tasks_source


def test_import_router_delegates_import_task_runtime_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/import_tasks.py"
    imports_source = (project_root / "app/routers/imports.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def run_bilibili_video_import" in service_source
    assert "async def run_local_video_import" in service_source
    assert "async def store_imported_video_content" in service_source
    assert "def delete_existing_import_vectors" in service_source
    assert "def cleanup_local_upload" in service_source
    assert "from app.services.import_tasks import" in imports_source
    assert "await run_bilibili_video_import(" in imports_source
    assert "await run_local_video_import(" in imports_source
    assert (
        "_store_imported_video_content = store_imported_video_content" in imports_source
    )
    assert "select(VideoCache)" not in imports_source
    assert "VideoCache(" not in imports_source
    assert "FavoriteFolder(" not in imports_source
    assert "FavoriteVideo(" not in imports_source
    assert "VideoContent(" not in imports_source
    assert "rag.add_video_content(" not in imports_source


def test_scoped_folder_sync_tests_do_not_import_legacy_router():
    project_root = get_project_root()

    for relative_path in [
        "tests/test_knowledge_base_scoping.py",
        "tests/test_folder_ingestion.py",
    ]:
        test_file = project_root / relative_path
        if not test_file.exists():
            continue
        source = test_file.read_text(encoding="utf-8")
        assert "from app.routers.knowledge import _sync_folder" not in source
