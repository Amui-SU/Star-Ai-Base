from tests.service_boundaries.helpers import function_source
from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import declared_module_names
from tests.service_boundaries.helpers import get_project_root


def test_favorites_router_delegates_listing_runtime_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/favorites_route_runtime.py"
    router_source = (project_root / "app/routers/favorites.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in {
        "list_legacy_favorite_folders",
        "list_legacy_favorite_videos",
        "list_all_legacy_favorite_videos",
    }:
        assert f"async def {name}" in service_source

    assert "from app.services.favorites_route_runtime import" in router_source

    list_route_source = function_source(router_source, "get_favorites_list")
    paged_route_source = function_source(router_source, "get_favorite_videos")
    all_route_source = function_source(router_source, "get_all_favorite_videos")

    for source in (list_route_source, paged_route_source, all_route_source):
        assert "await get_session(" not in source
        assert "bilibili_service_from_cookies(" not in source
        assert "await bili.close()" not in source

    assert "get_user_favorites(" not in list_route_source
    assert "FavoriteFolderInfo(" not in list_route_source
    assert "get_favorite_content(" not in paged_route_source
    assert '"is_selected": True' not in paged_route_source
    assert "bili.get_all_favorite_videos(" not in all_route_source
    assert 'title in ["已失效视频", "已删除视频"]' not in all_route_source


def test_favorites_router_delegates_organize_runtime_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/favorites_route_runtime.py"
    router_source = (project_root / "app/routers/favorites.py").read_text(
        encoding="utf-8"
    )

    service_source = service_path.read_text(encoding="utf-8")
    for name in {
        "preview_legacy_favorite_organization",
        "execute_legacy_favorite_organization",
        "clean_legacy_favorite_invalid_resources",
    }:
        assert f"async def {name}" in service_source

    preview_source = function_source(router_source, "organize_preview")
    execute_source = function_source(router_source, "organize_execute")
    clean_source = function_source(router_source, "clean_invalid_resources")

    for source in (preview_source, execute_source, clean_source):
        assert "await get_session(" not in source
        assert "bilibili_service_from_cookies(" not in source
        assert "await bili.close()" not in source

    assert "get_user_favorites(" not in preview_source
    assert "get_all_favorite_videos(" not in preview_source
    assert "items_data" not in preview_source
    assert "move_groups" not in execute_source
    assert "move_favorite_resources(" not in execute_source
    assert "clean_favorite_resources(" not in clean_source


def test_favorite_runtimes_share_video_presenter_helpers():
    project_root = get_project_root()
    helper_path = project_root / "app/services/favorite_video_presenters.py"
    legacy_path = project_root / "app/services/favorites_route_runtime.py"
    source_binding_path = project_root / "app/services/source_binding_favorites.py"

    assert helper_path.exists()
    helper_source = helper_path.read_text(encoding="utf-8")
    for name in {
        "favorite_video_summary",
        "legacy_valid_favorite_video_summary",
        "source_binding_valid_favorite_video_summary",
        "favorite_organize_candidate",
        "source_binding_favorite_organization_item",
        "dedupe_favorite_organization_items",
    }:
        assert f"def {name}" in helper_source

    legacy_source = legacy_path.read_text(encoding="utf-8")
    source_binding_source = source_binding_path.read_text(encoding="utf-8")

    assert "from app.services.favorite_video_presenters import" in legacy_source
    assert "from app.services.favorite_video_presenters import" in source_binding_source

    assert "INVALID_FAVORITE_VIDEO_TITLES" not in declared_module_names(legacy_source)
    assert declared_callable_names(legacy_source).isdisjoint(
        {
            "favorite_video_summary",
            "valid_favorite_video_summary",
            "favorite_organize_candidate",
        }
    )
    assert declared_callable_names(source_binding_source).isdisjoint(
        {
            "_favorite_video_summary",
            "_valid_favorite_video_summary",
            "_organization_item",
            "_dedupe_organization_items",
        }
    )
