import ast
from pathlib import Path


def test_router_package_exports_registered_routers():
    import app.routers as routers

    project_root = Path(__file__).resolve().parents[1]
    main_source = (project_root / "app/main.py").read_text(encoding="utf-8")
    expected = {
        line.strip().removeprefix("app.include_router(").removesuffix(".router)")
        for line in main_source.splitlines()
        if line.strip().startswith("app.include_router(")
    }

    assert set(routers.__all__) == expected
    for router_name in expected:
        assert hasattr(routers, router_name)
        assert hasattr(getattr(routers, router_name), "router")


def test_primary_routers_do_not_import_legacy_knowledge_router():
    project_root = Path(__file__).resolve().parents[1]

    for relative_path in [
        "app/routers/knowledge_bases.py",
        "app/routers/imports.py",
        "app/routers/chat.py",
    ]:
        source = (project_root / relative_path).read_text(encoding="utf-8")
        assert "app.routers.knowledge import" not in source


def test_chat_router_does_not_keep_mutable_current_llm_provider():
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")

    assert "_current_llm_provider" not in source


def test_chat_router_delegates_configuration_boundaries_to_service():
    project_root = Path(__file__).resolve().parents[1]
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    chat_module = ast.parse(chat_source)

    declared_names = set()
    for node in chat_module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            declared_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    declared_names.add(target.id)

    assert (project_root / "app/services/chat_config.py").exists()
    assert "from app.services.chat_config import" in chat_source
    assert declared_names.isdisjoint(
        {
            "PROVIDER_META",
            "PROVIDER_ENV_FIELDS",
            "SETTINGS_FIELD_BY_ENV",
            "PROVIDER_THINKING_SETTINGS_FIELDS",
            "PROVIDER_THINKING_TEMPLATES",
            "SUPPORTED_WEB_SEARCH_PROVIDERS",
            "SUPPORTED_TAVILY_SEARCH_DEPTHS",
            "_normalize_provider",
            "_current_default_llm_provider",
            "_resolve_llm_config",
            "_get_provider_thinking_template",
            "_parse_thinking_config",
            "_get_provider_thinking_config",
            "_env_file_path",
            "_read_env_values",
            "_write_env_values",
            "_normalize_web_search_provider",
            "_normalize_tavily_search_depth",
            "_web_search_config_response",
        }
    )


def test_favorite_router_uses_shared_default_folder_detection():
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "app/routers/favorites.py").read_text(encoding="utf-8")

    assert "def _is_default_folder" not in source
    assert "is_legacy_default_favorite_folder" in source


def test_system_auth_router_uses_logger_for_tracebacks():
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "app/routers/system_auth.py").read_text(encoding="utf-8")

    assert "traceback.print_exc" not in source
    assert "import traceback" not in source


def test_database_legacy_migration_entrypoint_has_no_nested_helpers():
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "app/database.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    target = next(
        node
        for node in module.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "_ensure_sqlite_legacy_columns"
    )

    nested_helpers = [
        node.name
        for node in ast.walk(target)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node is not target
    ]

    assert nested_helpers == []


def test_ingestion_task_persistence_and_status_mapping_live_in_service():
    project_root = Path(__file__).resolve().parents[1]
    service_source = (project_root / "app/services/ingestion_tasks.py").read_text(
        encoding="utf-8"
    )
    imports_source = (project_root / "app/routers/imports.py").read_text(
        encoding="utf-8"
    )
    knowledge_bases_source = (
        project_root / "app/routers/knowledge_bases.py"
    ).read_text(encoding="utf-8")

    assert "def build_status_payload" in service_source
    assert "async def create_ingestion_task" in service_source
    assert "from app.services.ingestion_tasks import" in imports_source
    assert "from app.services.ingestion_tasks import" in knowledge_bases_source
    assert "async def _create_import_task" not in imports_source
    assert "return build_status_payload(task)" in knowledge_bases_source
    assert '"processed_videos": task.processed_items' not in knowledge_bases_source
