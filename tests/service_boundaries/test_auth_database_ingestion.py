from tests.service_boundaries.helpers import get_project_root


def test_auth_database_ingestion_boundary_file_delegates_to_focused_files():
    project_root = get_project_root()
    service_boundary_dir = project_root / "tests" / "service_boundaries"

    for file_name in [
        "test_system_auth_router.py",
        "test_database_boundaries.py",
        "test_legacy_bilibili_session_boundaries.py",
        "test_ingestion_boundaries.py",
        "test_content_fetcher_boundaries.py",
        "test_asr_boundaries.py",
        "test_bilibili_service_boundaries.py",
        "test_favorites_router_boundaries.py",
    ]:
        assert (service_boundary_dir / file_name).exists()
