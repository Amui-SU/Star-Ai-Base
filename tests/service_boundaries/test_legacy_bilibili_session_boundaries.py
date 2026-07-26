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
    declared_names = declared_callable_names(auth_source)

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    expected_service_names = {
        "login_sessions",
        "_set_session",
        "_get_session",
    }
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"{name}:" in service_source

    # 绑定二维码流程仍使用进程内热缓存；旧登录/收藏夹路由已降级为 410 stub
    assert "from app.services.legacy_bilibili_sessions import" in source_bindings_source
    assert "from app.services.legacy_bilibili_sessions import" not in auth_source
    assert "from app.services.legacy_bilibili_sessions import" not in favorites_source
    assert "from app.routers.auth import" not in source_bindings_source
    assert declared_names.isdisjoint(
        {
            "_cleanup_expired_sessions",
            "_set_session",
            "_get_session",
            "get_session",
        }
    )
