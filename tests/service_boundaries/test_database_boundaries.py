import ast

from tests.service_boundaries.helpers import get_project_root


def test_database_legacy_migration_entrypoint_delegates_without_nested_helpers():
    project_root = get_project_root()
    source = (project_root / "app/database.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    target = next(
        node
        for node in module.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "init_db"
    )

    nested_helpers = [
        node.name
        for node in ast.walk(target)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node is not target
    ]

    assert nested_helpers == []
    assert "_ensure_sqlite_legacy_columns = ensure_sqlite_legacy_columns" in source


def test_database_delegates_sqlite_legacy_schema_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/sqlite_legacy_schema.py"
    database_source = (project_root / "app/database.py").read_text(encoding="utf-8")

    expected_service_names = {
        "SQLITE_LEGACY_COLUMNS",
        "ensure_sqlite_legacy_columns",
        "ensure_sqlite_legacy_schema_sync",
        "sqlite_add_missing_legacy_columns",
        "sqlite_rebuild_video_cache_without_unique_bvid",
        "sqlite_create_video_cache_indexes",
        "sqlite_clone_scoped_video_cache_rows",
        "sqlite_create_api_account_indexes",
        "sqlite_create_chat_history_indexes",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"{name}:" in service_source

    assert "from app.services.sqlite_legacy_schema import" in database_source
    assert (
        "_ensure_sqlite_legacy_columns = ensure_sqlite_legacy_columns"
        in database_source
    )
    assert "PRAGMA table_info" not in database_source
    assert "CREATE UNIQUE INDEX IF NOT EXISTS" not in database_source
    assert 'CREATE TABLE "video_cache_new"' not in database_source
    assert "SQLITE_LEGACY_COLUMNS: dict" not in database_source
