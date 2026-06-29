from tests.service_boundaries.helpers import get_project_root


def test_knowledge_base_web_search_helper_tests_are_split_from_scoping_file():
    project_root = get_project_root()
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    web_search_test = project_root / "tests" / "test_knowledge_base_web_search.py"

    assert web_search_test.exists()
    web_search_source = web_search_test.read_text(encoding="utf-8")
    for test_name in [
        "test_web_search_context_is_marked_as_sandboxed_but_usable",
        "test_knowledge_base_prompt_is_strict_when_web_search_disabled",
        "test_knowledge_base_prompt_allows_general_knowledge_when_context_is_empty",
        "test_web_search_query_generation_adds_compact_query",
        "test_web_search_context_limits_results_used",
        "test_fetch_web_page_tool_limits_fetch_calls",
    ]:
        assert test_name not in scoping_source
        assert test_name in web_search_source


def test_knowledge_base_web_search_stream_tests_are_split_from_scoping_file():
    project_root = get_project_root()
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    streaming_test = (
        project_root / "tests" / "test_knowledge_base_web_search_streaming.py"
    )
    streaming_dir = project_root / "tests" / "knowledge_base_web_search_streaming"
    streaming_files = [
        streaming_dir / "test_stream_status.py",
        streaming_dir / "test_stream_heartbeats.py",
        streaming_dir / "test_stream_sources.py",
    ]

    assert streaming_test.exists()
    for streaming_file in streaming_files:
        assert streaming_file.exists()
    streaming_source = "\n".join(
        streaming_file.read_text(encoding="utf-8") for streaming_file in streaming_files
    )
    for test_name in [
        "test_scoped_chat_stream_reports_web_search_no_results",
        "test_scoped_chat_stream_reports_socks_dependency_failure",
        "test_scoped_chat_stream_emits_web_search_progress_before_tool_setup",
        "test_scoped_chat_stream_emits_web_search_heartbeat_while_preparing",
        "test_web_search_heartbeat_generator_cancels_prepare_task_on_close",
        "test_web_search_heartbeat_generator_times_out_tool_setup",
        "test_web_search_tool_prep_timeout_allows_slow_model_tool_planning",
        "test_scoped_chat_stream_adds_web_sources_from_initial_search",
        "test_scoped_chat_stream_uses_final_stream_after_tool_decision",
    ]:
        assert test_name not in scoping_source
        assert test_name in streaming_source


def test_knowledge_base_web_search_api_tests_are_split_from_scoping_file():
    project_root = get_project_root()
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    api_test = project_root / "tests" / "test_knowledge_base_web_search_api.py"
    api_dir = project_root / "tests" / "knowledge_base_web_search_api"

    assert api_test.exists()
    api_source = api_test.read_text(encoding="utf-8")
    assert (
        "test_knowledge_base_web_search_api_tests_delegate_to_focused_files"
        in api_source
    )
    assert len(api_source.splitlines()) <= 80
    focused_source = "\n".join(
        (api_dir / relative_path).read_text(encoding="utf-8")
        for relative_path in [
            "test_tool_chain.py",
            "test_fetch_page.py",
            "test_toggle_fallback.py",
        ]
    )
    for test_name in [
        "test_scoped_chat_lets_llm_call_web_search_tool_when_enabled",
        "test_scoped_chat_reports_socks_dependency_failure",
        "test_scoped_chat_web_search_tool_chain_executes_model_requested_query",
        "test_scoped_chat_web_search_tool_accepts_query_alias_arguments",
        "test_scoped_chat_tool_chain_can_fetch_selected_web_page",
        "test_scoped_chat_direct_fetch_tool_reports_page_source",
        "test_scoped_chat_does_not_web_search_by_default",
        "test_scoped_chat_forces_web_search_when_enabled_without_model_tool_call",
    ]:
        assert test_name not in scoping_source
        assert test_name in focused_source


def test_knowledge_base_web_search_tool_run_tests_are_split_from_scoping_file():
    project_root = get_project_root()
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    tool_run_test = (
        project_root / "tests" / "test_knowledge_base_web_search_tool_run.py"
    )

    assert tool_run_test.exists()
    tool_run_source = tool_run_test.read_text(encoding="utf-8")
    for test_name in [
        "test_initial_web_context_is_not_duplicated_after_tool_run",
        "test_initial_web_search_no_results_is_visible_to_model",
        "test_web_search_tool_run_uses_request_provider",
        "test_web_search_tool_run_uses_tavily_api_key",
        "test_initial_web_search_diagnostics_are_reported_when_search_fails",
        "test_only_new_tool_results_are_appended_after_initial_web_context",
        "test_tool_web_results_remove_initial_no_results_instruction",
    ]:
        assert test_name not in scoping_source
        assert test_name in tool_run_source


def test_knowledge_base_web_search_fallback_tests_are_split_from_scoping_file():
    project_root = get_project_root()
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    fallback_test = (
        project_root / "tests" / "test_knowledge_base_web_search_fallback.py"
    )

    assert fallback_test.exists()
    fallback_source = fallback_test.read_text(encoding="utf-8")
    for test_name in [
        "test_scoped_chat_web_search_does_not_attach_db_fallback_sources",
        "test_scoped_chat_does_not_use_db_fallback_when_vector_search_is_empty",
        "test_scoped_chat_adds_initial_web_sources_to_first_answer_context",
        "test_scoped_chat_can_use_web_search_when_knowledge_base_has_no_hits",
    ]:
        assert test_name not in scoping_source
        assert test_name in fallback_source


def test_knowledge_base_stream_tests_are_split_from_scoping_file():
    project_root = get_project_root()
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    stream_test = project_root / "tests" / "test_knowledge_base_streaming.py"

    assert stream_test.exists()
    stream_source = stream_test.read_text(encoding="utf-8")
    for test_name in [
        "test_scoped_chat_stream_requires_owned_knowledge_base",
        "test_scoped_chat_stream_returns_answer_for_owner",
        "test_scoped_chat_stream_json_encodes_thinking",
        "test_scoped_chat_stream_uses_configured_thinking",
        "test_scoped_chat_stream_emits_empty_sources_trailer",
    ]:
        assert test_name not in scoping_source
        assert test_name in stream_source


def test_knowledge_base_scope_build_tests_are_split_from_scoping_file():
    project_root = get_project_root()
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    scope_build_test = project_root / "tests" / "test_knowledge_base_scope_build.py"

    assert scope_build_test.exists()
    scope_build_source = scope_build_test.read_text(encoding="utf-8")
    for test_name in [
        "test_scoped_chat_unions_folder_and_explicit_video_scope",
        "test_scoped_search_passes_resolved_video_scope",
        "test_scoped_chat_stream_uses_same_resolved_scope",
        "test_scoped_chat_rejects_external_bvid",
        "test_scope_options_only_returns_current_knowledge_base",
        "test_scope_options_requires_login",
        "test_scope_options_hides_other_users_knowledge_base",
        "test_scoped_build_rejects_unknown_source_binding",
        "test_scoped_build_records_scope_metadata",
        "test_scoped_build_accepts_single_video_selection",
        "test_scoped_build_starts_when_vector_service_is_unavailable",
        "test_scoped_build_rejects_empty_folder_ids",
        "test_scoped_build_rejects_other_users_source_binding",
        "test_build_status_polling_does_not_touch_session_last_seen",
    ]:
        assert test_name not in scoping_source
        assert test_name in scope_build_source
