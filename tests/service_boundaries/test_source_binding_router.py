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


def test_source_binding_router_delegates_title_updates_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/source_binding_titles.py"
    router_source = (project_root / "app/routers/source_bindings.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def update_video_title_override" in service_source
    assert "from app.services.source_binding_titles import" in router_source
    assert "update_video_title_override(" in router_source
    assert "select(FavoriteVideo.id)" not in router_source
    assert "VideoTitleOverride(" not in router_source
    assert "VideoTitleOverride.workspace_id" not in router_source


def test_source_binding_router_delegates_authenticated_service_factory():
    project_root = get_project_root()
    service_path = project_root / "app/services/source_binding_services.py"
    router_source = (project_root / "app/routers/source_bindings.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def get_bilibili_service_for_binding" in service_source
    assert "from app.services.source_binding_services import" in router_source
    assert "_get_bilibili_service_for_binding" in router_source
    assert "select(SourceCredential)" not in router_source
    assert "decrypt_text(credential.encrypted_payload)" not in router_source
    assert "bilibili_service_from_cookies(payload" not in router_source
    assert "_get_bilibili_service_for_binding" not in declared_names


def test_source_binding_router_delegates_bilibili_qr_flow_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/source_binding_services.py"
    router_source = (project_root / "app/routers/source_bindings.py").read_text(
        encoding="utf-8"
    )
    service_source = service_path.read_text(encoding="utf-8")

    generate_route_source = router_source[
        router_source.index(
            "async def generate_bilibili_binding_qrcode("
        ) : router_source.index('@router.get("/bilibili/qrcode/poll')
    ]
    poll_route_source = router_source[
        router_source.index(
            "async def poll_bilibili_binding_qrcode("
        ) : router_source.index("# ── 收藏夹接口")
    ]

    assert "async def generate_bilibili_binding_qrcode" in service_source
    assert "async def poll_bilibili_binding_qrcode" in service_source
    assert "_generate_bilibili_binding_qrcode(" in generate_route_source
    assert "_poll_bilibili_binding_qrcode(" in poll_route_source

    for route_source in (generate_route_source, poll_route_source):
        assert "BilibiliService()" not in route_source
        assert "_create_pending_state(" not in route_source
        assert "_get_pending_state(" not in route_source
        assert "SourceBinding(" not in route_source
        assert "SourceCredential(" not in route_source
        assert "encrypt_text(" not in route_source
        assert "bilibili_service_from_cookies(" not in route_source


def test_source_binding_router_delegates_favorite_flows_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/source_binding_favorites.py"
    router_source = (project_root / "app/routers/source_bindings.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    expected_service_names = {
        "list_bilibili_favorite_folders",
        "list_bilibili_favorite_videos",
        "list_all_bilibili_favorite_videos",
        "preview_bilibili_favorite_organization",
        "execute_bilibili_favorite_moves",
        "clean_invalid_bilibili_favorite_resources",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"async def {name}" in service_source

    assert "from app.services.source_binding_favorites import" in router_source
    assert "FavoriteFolderInfo(" not in router_source
    assert "defaultdict(" not in router_source
    assert "get_user_favorites(" not in router_source
    assert "get_favorite_content(" not in router_source
    assert "get_all_favorite_videos(" not in router_source
    assert "move_favorite_resources(" not in router_source
    assert "clean_favorite_resources(" not in router_source
    assert "is_default_favorite_folder(" not in router_source
    assert declared_names.isdisjoint(expected_service_names)
