from tests.service_boundaries.helpers import get_project_root


def test_bilibili_service_delegates_cookie_and_response_helpers():
    project_root = get_project_root()
    cookie_service_path = project_root / "app/services/bilibili_cookies.py"
    response_service_path = project_root / "app/services/bilibili_responses.py"
    facade_service_path = project_root / "app/services/bilibili_service_mixins.py"
    bilibili_source = (project_root / "app/services/bilibili.py").read_text(
        encoding="utf-8"
    )

    assert cookie_service_path.exists()
    cookie_service_source = cookie_service_path.read_text(encoding="utf-8")
    assert "def service_kwargs_from_cookies" in cookie_service_source
    assert "def normalize_bilibili_cookies" in cookie_service_source
    assert "def bilibili_service_from_cookies" in cookie_service_source

    assert response_service_path.exists()
    response_service_source = response_service_path.read_text(encoding="utf-8")
    assert "def parse_bilibili_json_response" in response_service_source

    assert "from app.services.bilibili_cookies import" in bilibili_source
    assert "from app.services.bilibili_responses import" in bilibili_source
    assert facade_service_path.exists()
    facade_service_source = facade_service_path.read_text(encoding="utf-8")
    for name in {
        "BilibiliAuthMixin",
        "BilibiliFavoritesMixin",
        "BilibiliVideoMixin",
        "BilibiliMediaMixin",
    }:
        assert f"class {name}" in facade_service_source
    assert "from app.services.bilibili_service_mixins import" in bilibili_source
    assert "class BilibiliService(" in bilibili_source
    assert "def _service_kwargs_from_cookies" not in bilibili_source
    assert "def normalize_bilibili_cookies" not in bilibili_source
    assert "def bilibili_service_from_cookies" not in bilibili_source
    assert "def _parse_json_response" not in bilibili_source
    for method in {
        "generate_qrcode",
        "poll_qrcode_status",
        "get_user_info",
        "get_user_favorites",
        "get_favorite_content",
        "get_all_favorite_videos",
        "move_favorite_resources",
        "clean_favorite_resources",
        "get_video_info",
        "get_video_summary",
        "get_player_info",
        "get_audio_url",
        "download_subtitle",
        "download_audio_to_file",
    }:
        assert f"async def {method}" not in bilibili_source


def test_bilibili_service_delegates_media_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/bilibili_media.py"
    bilibili_source = (project_root / "app/services/bilibili.py").read_text(
        encoding="utf-8"
    )
    mixin_source = (project_root / "app/services/bilibili_service_mixins.py").read_text(
        encoding="utf-8"
    )

    expected_service_names = {
        "normalize_bilibili_media_url",
        "select_audio_url_from_playurl_payload",
        "subtitle_text_from_payload",
        "download_bilibili_audio_to_file",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"async def {name}" in service_source
    assert "from app.services.bilibili_media import" in mixin_source
    assert "def _bw(" not in bilibili_source
    assert 'subtitle_url.startswith("//")' not in bilibili_source
    assert 'for item in data.get("body", [])' not in bilibili_source


def test_bilibili_service_delegates_favorite_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/bilibili_favorites.py"
    bilibili_source = (project_root / "app/services/bilibili.py").read_text(
        encoding="utf-8"
    )
    mixin_source = (project_root / "app/services/bilibili_service_mixins.py").read_text(
        encoding="utf-8"
    )

    expected_service_names = {
        "get_bilibili_user_favorites",
        "get_bilibili_favorite_content",
        "get_all_bilibili_favorite_videos",
        "move_bilibili_favorite_resources",
        "clean_bilibili_favorite_resources",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"async def {name}" in service_source
    assert "from app.services.bilibili_favorites import" in mixin_source
    assert "/x/v3/fav/folder/created/list-all" not in bilibili_source
    assert "/x/v3/fav/resource/list" not in bilibili_source
    assert "/x/v3/fav/resource/move" not in bilibili_source
    assert "/x/v3/fav/resource/clean" not in bilibili_source
    assert '",".join(resources)' not in bilibili_source
    assert "while True" not in bilibili_source


def test_bilibili_service_delegates_video_api_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/bilibili_video.py"
    bilibili_source = (project_root / "app/services/bilibili.py").read_text(
        encoding="utf-8"
    )
    mixin_source = (project_root / "app/services/bilibili_service_mixins.py").read_text(
        encoding="utf-8"
    )

    expected_service_names = {
        "get_bilibili_video_info",
        "get_bilibili_video_summary",
        "get_bilibili_player_info",
        "get_bilibili_audio_url",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"async def {name}" in service_source
    assert "from app.services.bilibili_video import" in mixin_source
    assert '/x/web-interface/view"' not in bilibili_source
    assert "/x/web-interface/view/conclusion/get" not in bilibili_source
    assert "/x/player/wbi/v2" not in bilibili_source
    assert "/x/player/v2" not in bilibili_source
    assert "/x/player/wbi/playurl" not in bilibili_source
    assert "/x/player/playurl" not in bilibili_source
    assert "wbi_signer.sign(" not in bilibili_source


def test_bilibili_service_delegates_auth_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/bilibili_auth.py"
    bilibili_source = (project_root / "app/services/bilibili.py").read_text(
        encoding="utf-8"
    )
    mixin_source = (project_root / "app/services/bilibili_service_mixins.py").read_text(
        encoding="utf-8"
    )

    expected_service_names = {
        "generate_bilibili_qrcode",
        "poll_bilibili_qrcode_status",
        "get_bilibili_user_info",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"async def {name}" in service_source
    assert "from app.services.bilibili_auth import" in mixin_source
    assert "/x/passport-login/web/qrcode/generate" not in bilibili_source
    assert "/x/passport-login/web/qrcode/poll" not in bilibili_source
    assert "/x/web-interface/nav" not in bilibili_source
    assert "qrcode.QRCode(" not in bilibili_source
    assert "base64.b64encode" not in bilibili_source
    assert "urllib.parse" not in bilibili_source
