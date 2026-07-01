from tests.service_boundaries.split_guards.helpers import (
    assert_focused_files_contain_tests,
    assert_test_names_moved,
    combined_source,
    project_tests_dir,
    read_optional_source,
    read_source,
)


def test_knowledge_base_web_search_helper_tests_are_split_from_scoping_file():
    project_tests = project_tests_dir()
    scoping_source = read_source(project_tests / "test_knowledge_base_scoping.py")
    web_search_test = project_tests / "test_knowledge_base_web_search.py"

    assert web_search_test.exists()
    assert_test_names_moved(
        mixed_source=scoping_source,
        focused_source=read_source(web_search_test),
        test_names=[
            "test_web_search_context_is_marked_as_sandboxed_but_usable",
            "test_knowledge_base_prompt_is_strict_when_web_search_disabled",
            "test_knowledge_base_prompt_allows_general_knowledge_when_context_is_empty",
            "test_web_search_query_generation_adds_compact_query",
            "test_web_search_context_limits_results_used",
            "test_fetch_web_page_tool_limits_fetch_calls",
        ],
    )


def test_knowledge_base_web_search_stream_tests_are_split_from_scoping_file():
    project_tests = project_tests_dir()
    scoping_source = read_source(project_tests / "test_knowledge_base_scoping.py")
    streaming_test = project_tests / "test_knowledge_base_web_search_streaming.py"
    streaming_dir = project_tests / "knowledge_base_web_search_streaming"
    streaming_files = [
        streaming_dir / "test_stream_status.py",
        streaming_dir / "test_stream_heartbeats.py",
        streaming_dir / "test_stream_sources.py",
    ]

    assert streaming_test.exists()
    for streaming_file in streaming_files:
        assert streaming_file.exists()
    assert_test_names_moved(
        mixed_source=scoping_source,
        focused_source=combined_source(streaming_files),
        test_names=[
            "test_scoped_chat_stream_reports_web_search_no_results",
            "test_scoped_chat_stream_reports_socks_dependency_failure",
            "test_scoped_chat_stream_emits_web_search_progress_before_tool_setup",
            "test_scoped_chat_stream_emits_web_search_heartbeat_while_preparing",
            "test_web_search_heartbeat_generator_cancels_prepare_task_on_close",
            "test_web_search_heartbeat_generator_times_out_tool_setup",
            "test_web_search_tool_prep_timeout_allows_slow_model_tool_planning",
            "test_scoped_chat_stream_adds_web_sources_from_initial_search",
            "test_scoped_chat_stream_uses_final_stream_after_tool_decision",
        ],
    )


def test_knowledge_base_web_search_api_tests_are_split_from_scoping_file():
    project_tests = project_tests_dir()
    scoping_source = read_source(project_tests / "test_knowledge_base_scoping.py")
    api_test = project_tests / "test_knowledge_base_web_search_api.py"
    api_dir = project_tests / "knowledge_base_web_search_api"

    assert api_test.exists()
    api_source = read_source(api_test)
    assert (
        "test_knowledge_base_web_search_api_tests_delegate_to_focused_files"
        in api_source
    )
    assert len(api_source.splitlines()) <= 80
    assert_test_names_moved(
        mixed_source=scoping_source,
        focused_source=combined_source(
            [
                api_dir / "test_tool_chain_adapter_status.py",
                api_dir / "test_tool_chain_model_queries.py",
                api_dir / "test_fetch_page.py",
                api_dir / "test_toggle_fallback.py",
            ]
        ),
        test_names=[
            "test_scoped_chat_lets_llm_call_web_search_tool_when_enabled",
            "test_scoped_chat_reports_socks_dependency_failure",
            "test_scoped_chat_web_search_tool_chain_executes_model_requested_query",
            "test_scoped_chat_web_search_tool_accepts_query_alias_arguments",
            "test_scoped_chat_tool_chain_can_fetch_selected_web_page",
            "test_scoped_chat_direct_fetch_tool_reports_page_source",
            "test_scoped_chat_does_not_web_search_by_default",
            "test_scoped_chat_forces_web_search_when_enabled_without_model_tool_call",
        ],
    )


def test_knowledge_base_web_search_api_tool_chain_tests_are_split_by_domain():
    api_dir = project_tests_dir() / "knowledge_base_web_search_api"
    mixed_test = api_dir / "test_tool_chain.py"

    assert_focused_files_contain_tests(
        mixed_source=read_optional_source(mixed_test),
        focused_dir=api_dir,
        focused_files={
            "test_tool_chain_adapter_status.py": [
                "test_scoped_chat_lets_llm_call_web_search_tool_when_enabled",
                "test_scoped_chat_reports_socks_dependency_failure",
            ],
            "test_tool_chain_model_queries.py": [
                "test_scoped_chat_web_search_tool_chain_executes_model_requested_query",
                "test_scoped_chat_web_search_tool_accepts_query_alias_arguments",
            ],
        },
    )

    if mixed_test.exists():
        assert len(read_source(mixed_test).splitlines()) <= 80


def test_knowledge_base_web_search_tool_run_tests_are_split_from_scoping_file():
    project_tests = project_tests_dir()
    scoping_source = read_source(project_tests / "test_knowledge_base_scoping.py")
    tool_run_test = project_tests / "test_knowledge_base_web_search_tool_run.py"

    assert tool_run_test.exists()
    assert_test_names_moved(
        mixed_source=scoping_source,
        focused_source=read_source(tool_run_test),
        test_names=[
            "test_initial_web_context_is_not_duplicated_after_tool_run",
            "test_initial_web_search_no_results_is_visible_to_model",
            "test_web_search_tool_run_uses_request_provider",
            "test_web_search_tool_run_uses_tavily_api_key",
            "test_initial_web_search_diagnostics_are_reported_when_search_fails",
            "test_only_new_tool_results_are_appended_after_initial_web_context",
            "test_tool_web_results_remove_initial_no_results_instruction",
        ],
    )


def test_knowledge_base_web_search_fallback_tests_are_split_from_scoping_file():
    project_tests = project_tests_dir()
    scoping_source = read_source(project_tests / "test_knowledge_base_scoping.py")
    fallback_test = project_tests / "test_knowledge_base_web_search_fallback.py"
    fallback_dir = project_tests / "knowledge_base_web_search_fallback"
    fallback_files = [
        fallback_dir / "test_db_fallback_isolation.py",
        fallback_dir / "test_initial_web_context.py",
        fallback_dir / "test_web_only_answer.py",
    ]

    assert fallback_test.exists()
    for fallback_file in fallback_files:
        assert fallback_file.exists()
    assert_test_names_moved(
        mixed_source=scoping_source,
        focused_source=combined_source(fallback_files),
        test_names=[
            "test_scoped_chat_web_search_does_not_attach_db_fallback_sources",
            "test_scoped_chat_does_not_use_db_fallback_when_vector_search_is_empty",
            "test_scoped_chat_adds_initial_web_sources_to_first_answer_context",
            "test_scoped_chat_can_use_web_search_when_knowledge_base_has_no_hits",
        ],
    )


def test_knowledge_base_web_search_fallback_tests_are_split_by_domain():
    project_tests = project_tests_dir()
    mixed_test = project_tests / "test_knowledge_base_web_search_fallback.py"

    assert_focused_files_contain_tests(
        mixed_source=read_optional_source(mixed_test),
        focused_dir=project_tests / "knowledge_base_web_search_fallback",
        focused_files={
            "test_db_fallback_isolation.py": [
                "test_scoped_chat_web_search_does_not_attach_db_fallback_sources",
                "test_scoped_chat_does_not_use_db_fallback_when_vector_search_is_empty",
            ],
            "test_initial_web_context.py": [
                "test_scoped_chat_adds_initial_web_sources_to_first_answer_context",
            ],
            "test_web_only_answer.py": [
                "test_scoped_chat_can_use_web_search_when_knowledge_base_has_no_hits",
            ],
        },
    )

    if mixed_test.exists():
        assert len(read_source(mixed_test).splitlines()) <= 80
