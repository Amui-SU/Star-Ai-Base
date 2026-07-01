from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import get_project_root


def test_system_auth_router_uses_logger_for_tracebacks():
    project_root = get_project_root()
    source = (project_root / "app/routers/system_auth.py").read_text(encoding="utf-8")

    assert "traceback.print_exc" not in source
    assert "import traceback" not in source


def test_system_auth_router_delegates_oauth_state_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/system_auth_oauth.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    expected_service_names = {
        "OAUTH_STATE_COOKIE_NAME",
        "frontend_origin_is_allowed",
        "normalize_frontend_origin",
        "frontend_url_from_request",
        "frontend_url_from_state",
        "oauth_signing_key",
        "make_oauth_state",
        "decode_oauth_state",
        "verify_oauth_state",
        "new_oauth_state_nonce",
        "set_oauth_state_cookie",
        "clear_oauth_state_cookie",
        "oauth_state_nonce_is_valid",
        "oauth_user_email",
    }
    router_private_names = {
        "_frontend_origin_is_allowed",
        "_normalize_frontend_origin",
        "_frontend_url_from_request",
        "_frontend_url_from_state",
        "_oauth_signing_key",
        "_make_oauth_state",
        "_decode_oauth_state",
        "_verify_oauth_state",
        "_new_oauth_state_nonce",
        "_set_oauth_state_cookie",
        "_clear_oauth_state_cookie",
        "_oauth_state_nonce_is_valid",
        "_oauth_user_email",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"{name} =" in service_source
    assert "from app.services.system_auth_oauth import" in router_source
    assert declared_names.isdisjoint(router_private_names)


def test_system_auth_router_delegates_oauth_flow_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/system_auth_oauth_flow.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    expected_service_names = {
        "GOOGLE_TOKEN_URL",
        "GOOGLE_USERINFO_URL",
        "WECHAT_TOKEN_URL",
        "WECHAT_USERINFO_URL",
        "QQ_TOKEN_URL",
        "QQ_ME_URL",
        "QQ_USERINFO_URL",
        "build_google_login_redirect",
        "build_wechat_login_redirect",
        "build_qq_login_redirect",
        "validate_oauth_callback_state",
        "upsert_oauth_user",
        "redirect_with_oauth_session",
        "google_redirect_uri",
        "wechat_redirect_uri",
        "qq_redirect_uri",
    }
    router_private_names = {
        "_upsert_oauth_user",
        "_redirect_with_oauth_session",
        "_google_redirect_uri",
        "_wechat_redirect_uri",
        "_qq_redirect_uri",
        "_validate_oauth_callback_state",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert (
            f"def {name}" in service_source
            or f"async def {name}" in service_source
            or f"{name} =" in service_source
        )
    assert "from app.services.system_auth_oauth_flow import" in router_source
    assert declared_names.isdisjoint(router_private_names)


def test_system_auth_router_delegates_oauth_provider_network_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/system_auth_oauth_providers.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )

    expected_service_names = {
        "fetch_google_oauth_user",
        "fetch_wechat_oauth_user",
        "fetch_qq_oauth_user",
        "oauth_system_proxy_url",
    }
    provider_url_names = {
        "GOOGLE_TOKEN_URL",
        "GOOGLE_USERINFO_URL",
        "WECHAT_TOKEN_URL",
        "WECHAT_USERINFO_URL",
        "QQ_TOKEN_URL",
        "QQ_ME_URL",
        "QQ_USERINFO_URL",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"async def {name}" in service_source
    assert "from app.services.system_auth_oauth_providers import" in router_source
    assert "_fetch_google_oauth_user(" in router_source
    assert "_fetch_wechat_oauth_user(" in router_source
    assert "_fetch_qq_oauth_user(" in router_source
    for name in provider_url_names:
        assert name not in router_source


def test_system_auth_router_delegates_email_code_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/system_auth_codes.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    expected_service_names = {
        "CODE_TTL_SECONDS",
        "MAX_ATTEMPTS",
        "IP_RATE_MAX",
        "IP_RATE_WINDOW",
        "ip_rate_limit",
        "check_rate_limit",
        "check_ip_rate_limit",
        "hash_code",
        "email_is_valid",
        "password_exceeds_bcrypt_limit",
    }
    router_private_names = {
        "_cleanup_rate_limits",
        "_check_rate_limit",
        "_check_ip_rate_limit",
        "_hash_code",
        "_password_exceeds_bcrypt_limit",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert (
            f"def {name}" in service_source
            or f"async def {name}" in service_source
            or f"{name} =" in service_source
        )
    assert "from app.services.system_auth_codes import" in router_source
    assert declared_names.isdisjoint(router_private_names)


def test_system_auth_router_delegates_send_code_flow_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/system_auth_codes.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )

    service_source = service_path.read_text(encoding="utf-8")
    assert "async def send_verification_code" in service_source
    assert "send_verification_code as _send_verification_code" in router_source
    assert "_send_verification_code(" in router_source
    assert "delete(VerificationCode)" not in router_source
    assert "secrets.randbelow" not in router_source
    assert "send_verification_email(" not in router_source
    assert "timedelta(seconds=_CODE_TTL_SECONDS)" not in router_source


def test_system_auth_router_delegates_registration_flow_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/system_auth_registration.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def register_system_user" in service_source
    assert "from app.services.system_auth_registration import" in router_source
    assert "register_system_user(" in router_source
    assert "select(VerificationCode)" not in router_source
    assert "SystemUser(" not in router_source
    assert "Workspace(" not in router_source
    assert "WorkspaceMember(" not in router_source
    assert "hash_password(" not in router_source


def test_system_auth_router_delegates_login_flow_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/system_auth_login.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def login_system_user" in service_source
    assert "from app.services.system_auth_login import" in router_source
    assert "login_system_user(" in router_source
    assert "select(SystemUser).where(SystemUser.email" not in router_source
    assert "verify_password(" not in router_source
    assert "def _invalid_credentials_exception" not in router_source
    assert "SystemAuthResponse(" not in router_source


def test_system_auth_router_delegates_account_flows_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/system_auth_account.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def logout_system_user" in service_source
    assert "async def current_system_user_response" in service_source
    assert "async def update_system_display_name" in service_source
    assert "from app.services.system_auth_account import" in router_source
    assert "logout_system_user(" in router_source
    assert "current_system_user_response(" in router_source
    assert "update_system_display_name(" in router_source
    assert "select(SystemSession)" not in router_source
    assert "hash_token(" not in router_source
    assert "clear_session_cookie(" not in router_source
    assert "session.revoked_at" not in router_source
    assert "user.display_name =" not in router_source
    assert "await db.refresh(user)" not in router_source


def test_system_auth_router_delegates_session_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/system_auth_sessions.py"
    account_service_path = project_root / "app/services/system_auth_account.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )
    account_service_source = (
        account_service_path.read_text(encoding="utf-8")
        if account_service_path.exists()
        else ""
    )
    declared_names = declared_callable_names(router_source)

    expected_service_names = {
        "session_token_from_request",
        "create_system_session",
        "get_primary_workspace",
        "get_current_user",
    }
    router_private_names = {
        "_session_token_from_request",
        "_create_system_session",
        "_get_primary_workspace",
        "_get_current_user",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"async def {name}" in service_source
    assert "from app.services.system_auth_sessions import" in (
        router_source + account_service_source
    )
    assert declared_names.isdisjoint(router_private_names)


def test_system_auth_router_delegates_admin_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/system_auth_admin.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    expected_service_names = {
        "configured_admin_emails",
        "is_admin_user",
        "admin_user_response",
        "get_current_admin_user",
        "list_admin_users",
        "update_admin_user_status",
        "reset_admin_user_password",
    }
    router_private_names = {
        "_configured_admin_emails",
        "_is_admin_user",
        "_admin_user_response",
        "_get_current_admin_user",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"async def {name}" in service_source
    assert "from app.services.system_auth_admin import" in router_source
    assert declared_names.isdisjoint(router_private_names)
