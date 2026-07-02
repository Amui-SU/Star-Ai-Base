from tests.service_boundaries.split_guards.helpers import (
    assert_focused_files_contain_tests,
    project_tests_dir,
    read_optional_source,
    read_source,
    service_boundary_dir,
)


def test_web_search_tavily_tests_are_split_by_domain():
    project_tests = project_tests_dir()
    mixed_test = project_tests / "test_web_search_tavily.py"

    assert_focused_files_contain_tests(
        mixed_source=read_optional_source(mixed_test),
        focused_dir=project_tests / "web_search_tavily",
        focused_files={
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
        },
    )

    if mixed_test.exists():
        assert len(read_source(mixed_test).splitlines()) <= 80


def test_source_binding_service_tests_are_split_by_domain():
    project_tests = project_tests_dir()
    mixed_test = project_tests / "test_source_binding_services.py"

    assert_focused_files_contain_tests(
        mixed_source=read_optional_source(mixed_test),
        focused_dir=project_tests / "source_binding_services",
        focused_files={
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
        },
    )

    if mixed_test.exists():
        assert len(read_source(mixed_test).splitlines()) <= 80


def test_folder_ingestion_tests_are_split_by_domain():
    project_tests = project_tests_dir()
    mixed_test = project_tests / "test_folder_ingestion.py"

    assert_focused_files_contain_tests(
        mixed_source=read_optional_source(mixed_test),
        focused_dir=project_tests / "folder_ingestion",
        focused_files={
            "test_helpers_and_records.py": [
                "test_sync_folder_progress_callback_annotation_matches_runtime_calls",
                "test_delete_video_vectors_for_scope_uses_matching_rag_delete_method",
                "test_folder_ingestion_content_helpers_select_cache_and_source_policy",
                "test_folder_ingestion_record_helpers_respect_scope",
            ],
            "test_empty_and_partial_sync.py": [
                "test_sync_folder_skips_deletion_when_nonempty_folder_returns_empty_list",
                "test_partial_folder_sync_keeps_existing_unselected_videos",
            ],
            "test_scoped_vector_rebuild.py": [
                "test_scoped_sync_rebuilds_missing_vectors_from_existing_cache",
                "test_scoped_sync_skips_reindex_when_old_vector_delete_fails",
            ],
        },
    )

    if mixed_test.exists():
        assert len(read_source(mixed_test).splitlines()) <= 80


def test_auth_database_ingestion_boundary_tests_are_split_by_domain():
    boundary_dir = service_boundary_dir()
    mixed_test = boundary_dir / "test_auth_database_ingestion.py"

    assert_focused_files_contain_tests(
        mixed_source=read_optional_source(mixed_test),
        focused_dir=boundary_dir,
        focused_files={
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
            "test_favorites_router_boundaries.py": [
                "test_favorites_router_delegates_listing_runtime_to_service",
            ],
        },
    )

    if mixed_test.exists():
        assert len(read_source(mixed_test).splitlines()) <= 80


def test_knowledge_base_router_boundary_tests_are_split_by_domain():
    boundary_dir = service_boundary_dir()
    mixed_test = boundary_dir / "test_knowledge_base_router.py"

    assert_focused_files_contain_tests(
        mixed_source=read_optional_source(mixed_test),
        focused_dir=boundary_dir,
        focused_files={
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
        },
    )

    if mixed_test.exists():
        assert len(read_source(mixed_test).splitlines()) <= 80


def test_chat_router_boundary_tests_are_split_by_domain():
    boundary_dir = service_boundary_dir()
    mixed_test = boundary_dir / "test_chat_router.py"

    assert_focused_files_contain_tests(
        mixed_source=read_optional_source(mixed_test),
        focused_dir=boundary_dir,
        focused_files={
            "test_chat_router_config_boundaries.py": [
                "test_chat_router_does_not_keep_mutable_current_llm_provider",
                "test_chat_router_delegates_configuration_boundaries_to_service",
                "test_chat_router_delegates_global_config_writes_to_service",
                "test_chat_config_delegates_env_persistence_to_helper",
                "test_chat_config_delegates_web_search_config_to_helper",
                "test_chat_config_delegates_provider_catalog_to_helper",
                "test_chat_config_delegates_provider_config_writes_to_helper",
                "test_chat_router_uses_admin_service_instead_of_system_auth_router",
            ],
            "test_chat_router_llm_message_boundaries.py": [
                "test_chat_router_delegates_llm_tool_helpers_to_service",
                "test_chat_router_delegates_message_helpers_to_service",
                "test_chat_router_delegates_question_routing_helpers_to_service",
                "test_chat_router_delegates_completion_helpers_to_service",
                "test_chat_router_delegates_llm_client_factory_to_service",
            ],
            "test_chat_router_context_runtime_boundaries.py": [
                "test_chat_router_delegates_video_context_helpers_to_service",
                "test_chat_router_delegates_message_preparation_to_service",
                "test_chat_router_delegates_legacy_ask_runtime_to_service",
            ],
        },
    )

    if mixed_test.exists():
        assert len(read_source(mixed_test).splitlines()) <= 80
