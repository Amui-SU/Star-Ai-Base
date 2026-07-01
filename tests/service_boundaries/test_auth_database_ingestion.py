import ast

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


def test_database_legacy_migration_entrypoint_has_no_nested_helpers():
    project_root = get_project_root()
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
        "from app.services.legacy_bilibili_sessions import" in legacy_knowledge_source
    )
    assert "from app.routers.auth import" not in source_bindings_source
    assert "from app.routers.auth import get_session" not in favorites_source
    assert "from app.routers.auth import get_session" not in legacy_knowledge_source
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


def test_ingestion_task_persistence_and_status_mapping_live_in_service():
    project_root = get_project_root()
    service_source = (project_root / "app/services/ingestion_tasks.py").read_text(
        encoding="utf-8"
    )
    imports_source = (project_root / "app/routers/imports.py").read_text(
        encoding="utf-8"
    )
    import_tasks_source = (project_root / "app/services/import_tasks.py").read_text(
        encoding="utf-8"
    )
    build_tasks_source = (
        project_root / "app/services/knowledge_base_build_tasks.py"
    ).read_text(encoding="utf-8")
    build_requests_source = (
        project_root / "app/services/knowledge_base_build_requests.py"
    ).read_text(encoding="utf-8")
    knowledge_bases_source = (
        project_root / "app/routers/knowledge_bases.py"
    ).read_text(encoding="utf-8")

    assert "def build_status_payload" in service_source
    assert "async def create_ingestion_task" in service_source
    assert "async def update_ingestion_task" in service_source
    assert "from app.services.ingestion_tasks import" in imports_source
    assert "from app.services.ingestion_tasks import" in build_requests_source
    assert "async def _create_import_task" not in imports_source
    assert "async def _update_import_task" not in imports_source
    assert "async def _update_task" not in knowledge_bases_source
    assert "update_ingestion_task" in import_tasks_source
    assert "create_ingestion_task(" in build_requests_source
    assert "create_ingestion_task(" not in knowledge_bases_source
    assert "update_task: TaskUpdater = update_ingestion_task" in build_tasks_source


def test_import_router_delegates_import_task_runtime_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/import_tasks.py"
    imports_source = (project_root / "app/routers/imports.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def run_bilibili_video_import" in service_source
    assert "async def run_local_video_import" in service_source
    assert "async def store_imported_video_content" in service_source
    assert "def delete_existing_import_vectors" in service_source
    assert "def cleanup_local_upload" in service_source
    assert "from app.services.import_tasks import" in imports_source
    assert "await run_bilibili_video_import(" in imports_source
    assert "await run_local_video_import(" in imports_source
    assert (
        "_store_imported_video_content = store_imported_video_content" in imports_source
    )
    assert "select(VideoCache)" not in imports_source
    assert "VideoCache(" not in imports_source
    assert "FavoriteFolder(" not in imports_source
    assert "FavoriteVideo(" not in imports_source
    assert "VideoContent(" not in imports_source
    assert "rag.add_video_content(" not in imports_source


def test_content_fetcher_delegates_ai_summary_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/content_summary.py"
    fetcher_source = (project_root / "app/services/content_fetcher.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "def parse_ai_summary_result" in service_source
    assert "def format_ai_summary_content" in service_source
    assert "from app.services.content_summary import" in fetcher_source
    assert 'model_result.get("outline"' not in fetcher_source
    assert 'for item in summary["outline"]' not in fetcher_source
    assert 'for point in item.get("part_outline"' not in fetcher_source


def test_content_fetcher_delegates_subtitle_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/content_subtitles.py"
    fetcher_source = (project_root / "app/services/content_fetcher.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in {
        "extract_subtitles",
        "extract_subtitle_url",
        "pick_preferred_subtitle",
        "try_bilibili_subtitle",
    }:
        assert f"def {name}" in service_source or f"async def {name}" in service_source

    assert "from app.services.content_subtitles import" in fetcher_source
    assert "def pick_subtitle(" not in fetcher_source
    assert "def extract_subtitles(" not in fetcher_source
    assert "def extract_url(" not in fetcher_source
    assert "download_subtitle(" not in fetcher_source
    assert "get_player_info(" not in fetcher_source


def test_bilibili_service_delegates_cookie_and_response_helpers():
    project_root = get_project_root()
    cookie_service_path = project_root / "app/services/bilibili_cookies.py"
    response_service_path = project_root / "app/services/bilibili_responses.py"
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
    assert "def _service_kwargs_from_cookies" not in bilibili_source
    assert "def normalize_bilibili_cookies" not in bilibili_source
    assert "def bilibili_service_from_cookies" not in bilibili_source
    assert "def _parse_json_response" not in bilibili_source


def test_scoped_folder_sync_tests_do_not_import_legacy_router():
    project_root = get_project_root()

    for relative_path in [
        "tests/test_knowledge_base_scoping.py",
        "tests/test_folder_ingestion.py",
    ]:
        test_file = project_root / relative_path
        if not test_file.exists():
            continue
        source = test_file.read_text(encoding="utf-8")
        assert "from app.routers.knowledge import _sync_folder" not in source
