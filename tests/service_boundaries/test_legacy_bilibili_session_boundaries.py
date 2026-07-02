from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import get_project_root


def test_legacy_bilibili_session_helpers_live_in_service_not_auth_router():
    project_root = get_project_root()
    service_path = project_root / "app/services/legacy_bilibili_sessions.py"
    auth_source = (project_root / "app/routers/auth.py").read_text(encoding="utf-8")
    source_bindings_source = (
        project_root / "app/routers/source_bindings.py"
    ).read_text(encoding="utf-8")
    favorites_source = (project_root / "app/routers/favorites.py").read_text(
        encoding="utf-8"
    )
    legacy_knowledge_source = (project_root / "app/routers/knowledge.py").read_text(
        encoding="utf-8"
    )
    legacy_knowledge_runtime_source = (
        project_root / "app/services/knowledge_legacy_runtime.py"
    ).read_text(encoding="utf-8")
    declared_names = declared_callable_names(auth_source)

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    expected_service_names = {
        "login_sessions",
        "_set_session",
        "_get_session",
        "_encrypt_session_cookie",
        "_decrypt_session_cookie",
        "_cookies_from_db_session",
        "get_session",
    }
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"{name}:" in service_source

    assert "from app.services.legacy_bilibili_sessions import" in auth_source
    assert "from app.services.legacy_bilibili_sessions import" in source_bindings_source
    assert "from app.services.legacy_bilibili_sessions import" in favorites_source
    assert (
        "from app.services.legacy_bilibili_sessions import"
        in legacy_knowledge_runtime_source
    )
    assert (
        "from app.services.knowledge_legacy_runtime import" in legacy_knowledge_source
    )
    assert "from app.routers.auth import" not in source_bindings_source
    assert "from app.routers.auth import get_session" not in favorites_source
    assert "from app.routers.auth import get_session" not in legacy_knowledge_source
    assert (
        "from app.services.legacy_bilibili_sessions import"
        not in legacy_knowledge_source
    )
    assert declared_names.isdisjoint(
        {
            "_encrypt_session_cookie",
            "_decrypt_session_cookie",
            "_cookies_from_db_session",
            "_cleanup_expired_sessions",
            "_set_session",
            "_get_session",
            "get_session",
        }
    )
