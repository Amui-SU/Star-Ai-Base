from tests.service_boundaries.helpers import get_project_root


def test_tool_chain_file_delegates_to_focused_files():
    project_root = get_project_root()
    api_dir = project_root / "tests" / "knowledge_base_web_search_api"

    for file_name in [
        "test_tool_chain_adapter_status.py",
        "test_tool_chain_model_queries.py",
    ]:
        assert (api_dir / file_name).exists()
