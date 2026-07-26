from tests.service_boundaries.helpers import declared_module_names
from tests.service_boundaries.helpers import get_project_root


def test_chat_router_does_not_keep_mutable_current_llm_provider():
    project_root = get_project_root()
    source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")

    assert "_current_llm_provider" not in source


def test_chat_router_delegates_configuration_boundaries_to_service():
    project_root = get_project_root()
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    declared_names = declared_module_names(chat_source)
    service_source = (project_root / "app/services/chat_config.py").read_text(
        encoding="utf-8"
    )

    assert (project_root / "app/services/chat_config.py").exists()
    assert "async def llm_config_response" in service_source
    assert "def current_user_llm_source" in service_source
    assert "from app.services.chat_config import" in chat_source
    assert "UserApiAccount.user_id == current_user.id" not in chat_source
    assert "account_by_provider" not in chat_source
    assert "providers.append(" not in chat_source
    assert declared_names.isdisjoint(
        {
            "PROVIDER_META",
            "PROVIDER_ENV_FIELDS",
            "SETTINGS_FIELD_BY_ENV",
            "PROVIDER_THINKING_SETTINGS_FIELDS",
            "PROVIDER_THINKING_TEMPLATES",
            "SUPPORTED_WEB_SEARCH_PROVIDERS",
            "SUPPORTED_TAVILY_SEARCH_DEPTHS",
            "_normalize_provider",
            "_current_default_llm_provider",
            "_resolve_llm_config",
            "_get_provider_thinking_template",
            "_parse_thinking_config",
            "_get_provider_thinking_config",
            "_env_file_path",
            "_read_env_values",
            "_write_env_values",
            "_normalize_web_search_provider",
            "_normalize_tavily_search_depth",
            "_web_search_config_response",
        }
    )


def test_chat_router_delegates_global_config_writes_to_service():
    project_root = get_project_root()
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    service_source = (project_root / "app/services/chat_config.py").read_text(
        encoding="utf-8"
    )
    web_search_service_source = (
        project_root / "app/services/chat_web_search_config.py"
    ).read_text(encoding="utf-8")
    provider_config_service_source = (
        project_root / "app/services/chat_provider_config.py"
    ).read_text(encoding="utf-8")

    web_search_route_source = chat_source[
        chat_source.index("async def save_web_search_config(") : chat_source.index(
            "_llm_config_response = llm_config_response"
        )
    ]
    provider_config_route_source = chat_source[
        chat_source.index("async def save_llm_provider_config(") : chat_source.index(
            '@router.post("/llm/config")'
        )
    ]
    provider_switch_route_source = chat_source[
        chat_source.index("async def set_llm_config(") : chat_source.index(
            '@router.get("/health/llm")'
        )
    ]

    assert "def save_global_web_search_config" in web_search_service_source
    assert "save_global_web_search_config" in service_source
    assert "def save_global_llm_provider_config" in provider_config_service_source
    assert "def set_global_llm_provider" in provider_config_service_source
    assert "save_global_llm_provider_config" in service_source
    assert "set_global_llm_provider" in service_source

    assert "save_global_web_search_config(" in web_search_route_source
    assert "_write_env_values(" not in web_search_route_source
    assert "settings.web_search_provider =" not in web_search_route_source
    assert "updates = {" not in web_search_route_source

    assert "save_global_llm_provider_config(" in provider_config_route_source
    assert "_write_env_values(" not in provider_config_route_source
    assert "_verify_provider_configuration(" not in provider_config_route_source
    assert "json.dumps(" not in provider_config_route_source
    assert "reset_rag_service()" not in provider_config_route_source

    assert "set_global_llm_provider(" in provider_switch_route_source
    assert "_write_env_values(" not in provider_switch_route_source


def test_chat_router_delegates_llm_health_check_to_service():
    project_root = get_project_root()
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    service_path = project_root / "app/services/chat_health.py"
    service_source = service_path.read_text(encoding="utf-8")

    route_source = chat_source[
        chat_source.index("async def llm_health_check(") : chat_source.index(
            "_verify_provider_configuration ="
        )
    ]

    assert service_path.exists()
    assert "async def llm_health_response" in service_source
    assert "from app.services.chat_health import" in chat_source
    assert "llm_health_response(" in route_source
    assert "time.perf_counter(" not in route_source
    assert "client.chat.completions.create(" not in route_source
    assert "resolve_user_llm_credentials(" not in route_source
    assert "logger.warning(" not in route_source


def test_chat_config_delegates_env_persistence_to_helper():
    project_root = get_project_root()
    chat_config_source = (project_root / "app/services/chat_config.py").read_text(
        encoding="utf-8"
    )
    env_helper_path = project_root / "app/services/chat_config_env.py"

    assert env_helper_path.exists()
    env_helper_source = env_helper_path.read_text(encoding="utf-8")
    assert "SETTINGS_FIELD_BY_ENV = {" in env_helper_source
    assert "def _env_file_path" in env_helper_source
    assert "def _read_env_values" in env_helper_source
    assert "def _write_env_values" in env_helper_source
    assert "def write_env_values_to_path" in env_helper_source

    assert "from app.services.chat_config_env import" in chat_config_source
    assert "SETTINGS_FIELD_BY_ENV = {" not in chat_config_source
    assert "def _env_file_path" not in chat_config_source
    assert "def _read_env_values" not in chat_config_source
    assert "def _write_env_values" not in chat_config_source


def test_chat_config_delegates_web_search_config_to_helper():
    project_root = get_project_root()
    chat_config_source = (project_root / "app/services/chat_config.py").read_text(
        encoding="utf-8"
    )
    web_search_helper_path = project_root / "app/services/chat_web_search_config.py"

    assert web_search_helper_path.exists()
    web_search_helper_source = web_search_helper_path.read_text(encoding="utf-8")
    assert "SUPPORTED_WEB_SEARCH_PROVIDERS = " in web_search_helper_source
    assert "SUPPORTED_TAVILY_SEARCH_DEPTHS = " in web_search_helper_source
    assert "def _normalize_web_search_provider" in web_search_helper_source
    assert "def _normalize_tavily_search_depth" in web_search_helper_source
    assert "def _web_search_config_response" in web_search_helper_source
    assert "def save_global_web_search_config" in web_search_helper_source

    assert "from app.services.chat_web_search_config import" in chat_config_source
    assert "SUPPORTED_WEB_SEARCH_PROVIDERS = " not in chat_config_source
    assert "SUPPORTED_TAVILY_SEARCH_DEPTHS = " not in chat_config_source
    assert "def _normalize_web_search_provider" not in chat_config_source
    assert "def _normalize_tavily_search_depth" not in chat_config_source
    assert "def _web_search_config_response" not in chat_config_source
    assert "def save_global_web_search_config" not in chat_config_source


def test_chat_config_delegates_provider_catalog_to_helper():
    project_root = get_project_root()
    chat_config_source = (project_root / "app/services/chat_config.py").read_text(
        encoding="utf-8"
    )
    provider_helper_path = project_root / "app/services/chat_provider_catalog.py"

    assert provider_helper_path.exists()
    provider_helper_source = provider_helper_path.read_text(encoding="utf-8")
    assert "PROVIDER_META = {" in provider_helper_source
    assert "PROVIDER_ENV_FIELDS = {" in provider_helper_source
    assert "PROVIDER_THINKING_SETTINGS_FIELDS = {" in provider_helper_source
    assert "PROVIDER_THINKING_TEMPLATES = {" in provider_helper_source
    assert "def _normalize_provider" in provider_helper_source
    assert "def _current_default_llm_provider" in provider_helper_source
    assert "def _resolve_llm_config" in provider_helper_source
    assert "def _get_provider_thinking_template" in provider_helper_source
    assert "def _parse_thinking_config" in provider_helper_source
    assert "def _get_provider_thinking_config" in provider_helper_source

    assert "from app.services.chat_provider_catalog import" in chat_config_source
    assert "PROVIDER_META = {" not in chat_config_source
    assert "PROVIDER_ENV_FIELDS = {" not in chat_config_source
    assert "PROVIDER_THINKING_SETTINGS_FIELDS = {" not in chat_config_source
    assert "PROVIDER_THINKING_TEMPLATES = {" not in chat_config_source
    assert "def _normalize_provider" not in chat_config_source
    assert "def _current_default_llm_provider" not in chat_config_source
    assert "def _resolve_llm_config" not in chat_config_source
    assert "def _get_provider_thinking_template" not in chat_config_source
    assert "def _parse_thinking_config" not in chat_config_source
    assert "def _get_provider_thinking_config" not in chat_config_source


def test_chat_config_delegates_provider_config_writes_to_helper():
    project_root = get_project_root()
    chat_config_source = (project_root / "app/services/chat_config.py").read_text(
        encoding="utf-8"
    )
    provider_write_path = project_root / "app/services/chat_provider_config.py"

    assert provider_write_path.exists()
    provider_write_source = provider_write_path.read_text(encoding="utf-8")
    assert "def save_global_llm_provider_config" in provider_write_source
    assert "def set_global_llm_provider" in provider_write_source

    assert "from app.services.chat_provider_config import" in chat_config_source
    assert "def save_global_llm_provider_config" not in chat_config_source
    assert "def set_global_llm_provider" not in chat_config_source


def test_chat_router_uses_admin_service_instead_of_system_auth_router():
    project_root = get_project_root()
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")

    assert "from app.routers.system_auth import" not in chat_source
    assert "from app.services.system_auth_admin import" in chat_source
    assert "get_current_admin_user as _get_current_admin_user" in chat_source
