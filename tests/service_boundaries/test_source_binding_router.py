from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import get_project_root


def test_source_binding_router_delegates_presenter_and_title_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/source_binding_presenters.py"
    router_source = (project_root / "app/routers/source_bindings.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    expected_service_names = {
        "normalize_bvid",
        "normalize_custom_title",
        "get_video_title_overrides",
        "video_with_display_title",
        "source_binding_response",
    }
    router_private_names = {
        "_normalize_bvid",
        "_normalize_custom_title",
        "_get_video_title_overrides",
        "_with_display_title",
        "_response",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"async def {name}" in service_source
    assert "from app.services.source_binding_presenters import" in router_source
    assert "VideoTitleOverride.id.desc()" not in router_source
    assert declared_names.isdisjoint(router_private_names)


def test_source_binding_router_delegates_pending_state_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/source_binding_pending_states.py"
    router_source = (project_root / "app/routers/source_bindings.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    expected_service_names = {
        "create_pending_state",
        "get_pending_state",
        "delete_pending_state",
    }
    router_private_names = {
        "_create_pending_state",
        "_get_pending_state",
        "_delete_pending_state",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"async def {name}" in service_source
    assert "from app.services.source_binding_pending_states import" in router_source
    assert "OAuthPendingState.expires_at < now" not in router_source
    assert "OAuthPendingState.state_key == state_key" not in router_source
    assert declared_names.isdisjoint(router_private_names)
