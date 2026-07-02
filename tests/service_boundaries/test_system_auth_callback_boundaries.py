from tests.service_boundaries.helpers import function_source
from tests.service_boundaries.helpers import get_project_root


def test_system_auth_router_delegates_callback_runtime_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/system_auth_callback_runtime.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in {
        "email_config_status",
        "oauth_network_error",
        "handle_wechat_oauth_callback",
        "handle_qq_oauth_callback",
        "handle_google_oauth_callback",
    }:
        assert f"def {name}" in service_source or f"async def {name}" in service_source

    assert "from app.services.system_auth_callback_runtime import" in router_source
    assert "def _oauth_network_error" not in router_source

    email_config_source = function_source(router_source, "email_config_status")
    wechat_source = function_source(router_source, "wechat_callback")
    qq_source = function_source(router_source, "qq_callback")
    google_source = function_source(router_source, "google_callback")

    assert "smtp_configured =" not in email_config_source
    assert "_email_config_status(" in email_config_source

    for callback_source in {wechat_source, qq_source, google_source}:
        assert "_validate_oauth_callback_state(" not in callback_source
        assert "_redirect_with_oauth_session(" not in callback_source
        assert "_upsert_oauth_user(" not in callback_source
        assert "_oauth_network_error(" not in callback_source
        assert "except httpx.HTTPError" not in callback_source
        assert "logger.exception(" not in callback_source

    assert "_fetch_wechat_oauth_user(" not in wechat_source
    assert "_fetch_qq_oauth_user(" not in qq_source
    assert "_fetch_google_oauth_user(" not in google_source
    assert "verified_email" not in google_source
