from .helpers import get_project_root


def test_frontend_component_boundary_tests_are_split_by_domain():
    project_root = get_project_root()
    component_boundary_dir = project_root / "tests" / "frontend_structure"
    original_file = component_boundary_dir / "test_component_boundaries.py"

    expected_files = [
        "test_chat_component_boundaries.py",
        "test_account_import_component_boundaries.py",
        "test_auth_sources_workspace_component_boundaries.py",
    ]
    for file_name in expected_files:
        assert (component_boundary_dir / file_name).exists()

    original_source = original_file.read_text(encoding="utf-8")
    assert original_source.count("def test_") <= 2


def test_chat_component_boundary_tests_are_split_by_domain():
    project_root = get_project_root()
    component_boundary_dir = project_root / "tests" / "frontend_structure"
    original_file = component_boundary_dir / "test_chat_component_boundaries.py"

    expected_files = {
        "test_chat_panel_section_boundaries.py": [
            "test_chat_panel_uses_chat_subcomponents",
            "test_chat_panel_model_status_menu_is_extracted",
            "test_chat_panel_uses_header_section_component",
            "test_chat_panel_uses_composer_section_component",
            "test_frontend_provider_presets_are_shared",
        ],
        "test_chat_panel_hook_boundaries.py": [
            "test_chat_panel_uses_model_settings_hook",
            "test_chat_model_settings_hook_uses_state_helpers",
            "test_chat_panel_uses_web_search_settings_hook",
            "test_chat_panel_uses_conversation_history_hook",
            "test_chat_panel_uses_knowledge_context_hook",
            "test_chat_panel_uses_viewport_hook",
        ],
        "test_chat_streaming_boundaries.py": [
            "test_chat_streaming_uses_state_helpers",
            "test_chat_streaming_uses_runtime_helper",
        ],
        "test_chat_scope_message_boundaries.py": [
            "test_message_list_uses_focused_subcomponents",
            "test_chat_scope_picker_uses_focused_subcomponents",
        ],
        "test_chat_panel_test_suite_boundaries.py": [
            "test_chat_panel_history_tests_are_split_from_main_suite",
            "test_chat_panel_streaming_tests_are_split_from_main_suite",
            "test_chat_panel_web_search_tests_are_split_from_main_suite",
            "test_chat_panel_web_search_result_tests_are_split_from_toggle_suite",
            "test_chat_panel_config_tests_are_split_from_main_suite",
        ],
    }

    focused_source = ""
    for file_name, expected_tests in expected_files.items():
        focused_file = component_boundary_dir / file_name
        assert focused_file.exists()
        source = focused_file.read_text(encoding="utf-8")
        focused_source += source
        for test_name in expected_tests:
            assert f"def {test_name}" in source

    original_source = original_file.read_text(encoding="utf-8")
    assert original_source.count("def test_") <= 2
    for expected_tests in expected_files.values():
        for test_name in expected_tests:
            assert f"def {test_name}" not in original_source
            assert f"def {test_name}" in focused_source
