from .helpers import get_project_root


def test_chat_component_boundary_tests_are_split_by_domain():
    project_root = get_project_root()
    component_boundary_dir = project_root / "tests" / "frontend_structure"

    for file_name in [
        "test_chat_panel_section_boundaries.py",
        "test_chat_panel_hook_boundaries.py",
        "test_chat_streaming_boundaries.py",
        "test_chat_scope_message_boundaries.py",
        "test_chat_panel_test_suite_boundaries.py",
    ]:
        assert (component_boundary_dir / file_name).exists()
