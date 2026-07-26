from tests.service_boundaries.helpers import get_project_root


def test_chat_router_boundary_file_delegates_to_focused_files():
    service_boundary_dir = get_project_root() / "tests" / "service_boundaries"

    for file_name in [
        "test_chat_router_config_boundaries.py",
        "test_chat_router_llm_message_boundaries.py",
    ]:
        assert (service_boundary_dir / file_name).exists()
