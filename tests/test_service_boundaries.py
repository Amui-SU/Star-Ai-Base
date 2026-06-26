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
