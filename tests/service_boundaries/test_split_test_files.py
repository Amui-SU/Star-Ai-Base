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
            "test_tool_chain_adapter_status.py",
            "test_tool_chain_model_queries.py",
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


def test_knowledge_base_web_search_api_tool_chain_tests_are_split_by_domain():
    project_root = get_project_root()
    api_dir = project_root / "tests" / "knowledge_base_web_search_api"
    mixed_test = api_dir / "test_tool_chain.py"
    mixed_source = mixed_test.read_text(encoding="utf-8") if mixed_test.exists() else ""

    focused_files = {
        "test_tool_chain_adapter_status.py": [
            "test_scoped_chat_lets_llm_call_web_search_tool_when_enabled",
            "test_scoped_chat_reports_socks_dependency_failure",
        ],
        "test_tool_chain_model_queries.py": [
            "test_scoped_chat_web_search_tool_chain_executes_model_requested_query",
            "test_scoped_chat_web_search_tool_accepts_query_alias_arguments",
        ],
    }

    for file_name, test_names in focused_files.items():
        focused_path = api_dir / file_name
        assert focused_path.exists()
        focused_source = focused_path.read_text(encoding="utf-8")
        for test_name in test_names:
            assert test_name not in mixed_source
            assert test_name in focused_source

    if mixed_test.exists():
        assert len(mixed_source.splitlines()) <= 80


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
    fallback_dir = project_root / "tests" / "knowledge_base_web_search_fallback"
    fallback_files = [
        fallback_dir / "test_db_fallback_isolation.py",
        fallback_dir / "test_initial_web_context.py",
        fallback_dir / "test_web_only_answer.py",
    ]

    assert fallback_test.exists()
    for fallback_file in fallback_files:
        assert fallback_file.exists()
    fallback_source = "\n".join(
        fallback_file.read_text(encoding="utf-8") for fallback_file in fallback_files
    )
    for test_name in [
        "test_scoped_chat_web_search_does_not_attach_db_fallback_sources",
        "test_scoped_chat_does_not_use_db_fallback_when_vector_search_is_empty",
        "test_scoped_chat_adds_initial_web_sources_to_first_answer_context",
        "test_scoped_chat_can_use_web_search_when_knowledge_base_has_no_hits",
    ]:
        assert test_name not in scoping_source
        assert test_name in fallback_source


def test_knowledge_base_web_search_fallback_tests_are_split_by_domain():
    project_root = get_project_root()
    tests_dir = project_root / "tests"
    mixed_test = tests_dir / "test_knowledge_base_web_search_fallback.py"
    mixed_source = mixed_test.read_text(encoding="utf-8") if mixed_test.exists() else ""
    focused_dir = tests_dir / "knowledge_base_web_search_fallback"

    focused_files = {
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
    }

    for file_name, test_names in focused_files.items():
        focused_path = focused_dir / file_name
        assert focused_path.exists()
        focused_source = focused_path.read_text(encoding="utf-8")
        for test_name in test_names:
            assert test_name not in mixed_source
            assert test_name in focused_source

    if mixed_test.exists():
        assert len(mixed_source.splitlines()) <= 80


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
    tests_dir = project_root / "tests"
    scope_build_test = tests_dir / "test_knowledge_base_scope_build.py"
    focused_files = [
        tests_dir / "test_knowledge_base_scope_resolution.py",
        tests_dir / "test_knowledge_base_scope_options.py",
        tests_dir / "test_knowledge_base_build_requests.py",
        tests_dir / "test_knowledge_base_build_status.py",
    ]

    assert scope_build_test.exists()
    for focused_file in focused_files:
        assert focused_file.exists()
    focused_source = "\n".join(
        focused_file.read_text(encoding="utf-8") for focused_file in focused_files
    )
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
        assert test_name in focused_source


def test_knowledge_base_scope_build_tests_are_split_by_domain():
    project_root = get_project_root()
    tests_dir = project_root / "tests"
    mixed_test = tests_dir / "test_knowledge_base_scope_build.py"
    mixed_source = mixed_test.read_text(encoding="utf-8") if mixed_test.exists() else ""

    focused_files = {
        "test_knowledge_base_scope_resolution.py": [
            "test_scoped_chat_unions_folder_and_explicit_video_scope",
            "test_scoped_search_passes_resolved_video_scope",
            "test_scoped_chat_stream_uses_same_resolved_scope",
            "test_scoped_chat_rejects_external_bvid",
        ],
        "test_knowledge_base_scope_options.py": [
            "test_scope_options_only_returns_current_knowledge_base",
            "test_scope_options_requires_login",
            "test_scope_options_hides_other_users_knowledge_base",
        ],
        "test_knowledge_base_build_requests.py": [
            "test_scoped_build_rejects_unknown_source_binding",
            "test_scoped_build_records_scope_metadata",
            "test_scoped_build_accepts_single_video_selection",
            "test_scoped_build_starts_when_vector_service_is_unavailable",
            "test_scoped_build_rejects_empty_folder_ids",
            "test_scoped_build_rejects_other_users_source_binding",
        ],
        "test_knowledge_base_build_status.py": [
            "test_build_status_polling_does_not_touch_session_last_seen",
        ],
    }

    for file_name, test_names in focused_files.items():
        focused_path = tests_dir / file_name
        assert focused_path.exists()
        focused_source = focused_path.read_text(encoding="utf-8")
        for test_name in test_names:
            assert test_name not in mixed_source
            assert test_name in focused_source

    if mixed_test.exists():
        assert len(mixed_source.splitlines()) <= 80


def test_knowledge_scope_tests_are_split_by_domain():
    project_root = get_project_root()
    tests_dir = project_root / "tests"
    mixed_test = tests_dir / "test_knowledge_scope.py"
    mixed_source = mixed_test.read_text(encoding="utf-8") if mixed_test.exists() else ""
    focused_dir = tests_dir / "knowledge_scope"

    focused_files = {
        "test_catalog.py": [
            "test_protected_knowledge_base_list_requires_login",
            "test_user_can_create_and_list_own_knowledge_base",
        ],
        "test_rag_filters.py": [
            "test_scoped_rag_search_requires_workspace_and_knowledge_base_filter",
            "test_scoped_rag_search_adds_normalized_bvid_filter",
            "test_scoped_rag_search_keeps_legacy_filter_for_empty_scope",
        ],
        "test_delete_cleanup.py": [
            "test_delete_knowledge_base_keeps_record_when_vector_cleanup_fails",
            "test_delete_knowledge_base_does_not_retry_without_workspace_on_runtime_type_error",
            "test_delete_knowledge_base_removes_scoped_records_on_success",
        ],
        "test_db_fallback.py": [
            "test_chat_falls_back_to_database_content_when_vector_retrieval_fails",
        ],
    }

    for file_name, test_names in focused_files.items():
        focused_path = focused_dir / file_name
        assert focused_path.exists()
        focused_source = focused_path.read_text(encoding="utf-8")
        for test_name in test_names:
            assert test_name not in mixed_source
            assert test_name in focused_source

    if mixed_test.exists():
        assert len(mixed_source.splitlines()) <= 80


def test_web_search_tavily_tests_are_split_by_domain():
    project_root = get_project_root()
    tests_dir = project_root / "tests"
    mixed_test = tests_dir / "test_web_search_tavily.py"
    mixed_source = mixed_test.read_text(encoding="utf-8") if mixed_test.exists() else ""
    focused_dir = tests_dir / "web_search_tavily"

    focused_files = {
        "test_success_paths.py": [
            "test_search_web_uses_tavily_provider_when_configured",
            "test_search_web_keeps_tavily_snippets_when_dns_lookup_fails",
            "test_search_web_auto_uses_tavily_when_key_is_configured",
        ],
        "test_overrides.py": [
            "test_search_web_uses_tavily_api_key_override",
            "test_search_web_uses_request_provider_override",
        ],
        "test_fallbacks_and_failures.py": [
            "test_search_web_falls_back_to_html_when_tavily_fails",
            "test_search_web_returns_empty_without_html_fallback_when_tavily_fails",
            "test_search_web_reports_missing_tavily_key_without_html_fallback",
        ],
    }

    for file_name, test_names in focused_files.items():
        focused_path = focused_dir / file_name
        assert focused_path.exists()
        focused_source = focused_path.read_text(encoding="utf-8")
        for test_name in test_names:
            assert test_name not in mixed_source
            assert test_name in focused_source

    if mixed_test.exists():
        assert len(mixed_source.splitlines()) <= 80


def test_source_binding_service_tests_are_split_by_domain():
    project_root = get_project_root()
    tests_dir = project_root / "tests"
    mixed_test = tests_dir / "test_source_binding_services.py"
    mixed_source = mixed_test.read_text(encoding="utf-8") if mixed_test.exists() else ""
    focused_dir = tests_dir / "source_binding_services"

    focused_files = {
        "test_binding_catalog.py": [
            "test_list_source_bindings_returns_current_workspace_bindings_desc",
            "test_revoke_source_binding_marks_owned_workspace_binding_revoked",
            "test_revoke_source_binding_rejects_missing_or_foreign_binding",
            "test_ensure_active_source_binding_returns_owned_active_binding",
            "test_ensure_active_source_binding_rejects_revoked_binding",
        ],
        "test_binding_credentials.py": [
            "test_get_bilibili_service_for_binding_builds_service_from_credentials",
            "test_get_bilibili_service_for_binding_rejects_missing_binding",
            "test_get_bilibili_service_for_binding_rejects_missing_credentials",
            "test_get_bilibili_service_for_binding_wraps_decrypt_errors",
        ],
        "test_bilibili_qrcode.py": [
            "test_generate_bilibili_binding_qrcode_records_pending_state",
            "test_generate_bilibili_binding_qrcode_closes_service_on_failure",
            "test_poll_bilibili_binding_qrcode_confirms_and_clears_pending",
            "test_poll_bilibili_binding_qrcode_uses_persisted_pending_state",
        ],
    }

    for file_name, test_names in focused_files.items():
        focused_path = focused_dir / file_name
        assert focused_path.exists()
        focused_source = focused_path.read_text(encoding="utf-8")
        for test_name in test_names:
            assert test_name not in mixed_source
            assert test_name in focused_source

    if mixed_test.exists():
        assert len(mixed_source.splitlines()) <= 80


def test_auth_database_ingestion_boundary_tests_are_split_by_domain():
    project_root = get_project_root()
    service_boundary_dir = project_root / "tests" / "service_boundaries"
    mixed_test = service_boundary_dir / "test_auth_database_ingestion.py"
    mixed_source = mixed_test.read_text(encoding="utf-8") if mixed_test.exists() else ""

    focused_files = {
        "test_system_auth_router.py": [
            "test_system_auth_router_delegates_oauth_state_helpers_to_service",
            "test_system_auth_router_delegates_admin_helpers_to_service",
        ],
        "test_database_boundaries.py": [
            "test_database_legacy_migration_entrypoint_delegates_without_nested_helpers",
            "test_database_delegates_sqlite_legacy_schema_to_service",
        ],
        "test_legacy_bilibili_session_boundaries.py": [
            "test_legacy_bilibili_session_helpers_live_in_service_not_auth_router",
        ],
        "test_ingestion_boundaries.py": [
            "test_ingestion_task_persistence_and_status_mapping_live_in_service",
            "test_import_router_delegates_import_task_runtime_to_service",
            "test_scoped_folder_sync_tests_do_not_import_legacy_router",
        ],
        "test_content_fetcher_boundaries.py": [
            "test_content_fetcher_delegates_ai_summary_helpers_to_service",
            "test_content_fetcher_delegates_subtitle_helpers_to_service",
            "test_content_fetcher_delegates_asr_audio_helpers_to_service",
        ],
        "test_asr_boundaries.py": [
            "test_asr_service_delegates_audio_preparation_to_service",
            "test_asr_service_delegates_transcription_runtime_to_service",
        ],
        "test_bilibili_service_boundaries.py": [
            "test_bilibili_service_delegates_cookie_and_response_helpers",
            "test_bilibili_service_delegates_media_helpers_to_service",
            "test_bilibili_service_delegates_favorite_helpers_to_service",
        ],
    }

    for file_name, test_names in focused_files.items():
        focused_path = service_boundary_dir / file_name
        assert focused_path.exists()
        focused_source = focused_path.read_text(encoding="utf-8")
        for test_name in test_names:
            assert test_name not in mixed_source
            assert test_name in focused_source

    if mixed_test.exists():
        assert len(mixed_source.splitlines()) <= 80


def test_knowledge_base_router_boundary_tests_are_split_by_domain():
    project_root = get_project_root()
    service_boundary_dir = project_root / "tests" / "service_boundaries"
    mixed_test = service_boundary_dir / "test_knowledge_base_router.py"
    mixed_source = mixed_test.read_text(encoding="utf-8") if mixed_test.exists() else ""

    focused_files = {
        "test_knowledge_base_router_web_search_boundaries.py": [
            "test_knowledge_base_router_delegates_web_search_helpers_to_service",
            "test_knowledge_base_router_delegates_web_search_orchestration_to_service",
            "test_knowledge_base_router_uses_services_for_shared_llm_runtime",
            "test_knowledge_base_router_delegates_answer_completion_adapter_to_service",
        ],
        "test_knowledge_base_router_catalog_build_boundaries.py": [
            "test_knowledge_base_router_delegates_presenter_helpers_to_service",
            "test_knowledge_base_router_delegates_catalog_commands_to_service",
            "test_knowledge_base_router_delegates_message_helpers_to_service",
            "test_knowledge_base_router_delegates_scoped_document_loading_to_service",
            "test_knowledge_base_router_delegates_build_task_helpers_to_service",
            "test_knowledge_base_router_delegates_build_request_preparation_to_service",
            "test_knowledge_base_router_delegates_stats_helpers_to_service",
        ],
        "test_knowledge_base_router_chat_search_boundaries.py": [
            "test_knowledge_base_router_delegates_search_helpers_to_service",
            "test_knowledge_base_router_delegates_non_streaming_chat_to_service",
            "test_knowledge_base_router_delegates_streaming_chat_to_service",
        ],
        "test_knowledge_base_delete_boundaries.py": [
            "test_knowledge_base_router_delegates_record_deletion_to_service",
        ],
        "test_rag_ingestion_boundaries.py": [
            "test_folder_ingestion_delegates_records_and_content_helpers_to_services",
            "test_rag_service_delegates_document_and_filter_helpers_to_services",
            "test_favorite_router_uses_shared_default_folder_detection",
        ],
    }

    for file_name, test_names in focused_files.items():
        focused_path = service_boundary_dir / file_name
        assert focused_path.exists()
        focused_source = focused_path.read_text(encoding="utf-8")
        for test_name in test_names:
            assert test_name not in mixed_source
            assert test_name in focused_source

    if mixed_test.exists():
        assert len(mixed_source.splitlines()) <= 80
