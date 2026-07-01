from tests.service_boundaries.split_guards.helpers import (
    assert_focused_files_contain_tests,
    assert_test_names_moved,
    combined_source,
    project_tests_dir,
    read_optional_source,
    read_source,
)


def test_knowledge_base_stream_tests_are_split_from_scoping_file():
    project_tests = project_tests_dir()
    scoping_source = read_source(project_tests / "test_knowledge_base_scoping.py")
    stream_test = project_tests / "test_knowledge_base_streaming.py"

    assert stream_test.exists()
    assert_test_names_moved(
        mixed_source=scoping_source,
        focused_source=read_source(stream_test),
        test_names=[
            "test_scoped_chat_stream_requires_owned_knowledge_base",
            "test_scoped_chat_stream_returns_answer_for_owner",
            "test_scoped_chat_stream_json_encodes_thinking",
            "test_scoped_chat_stream_uses_configured_thinking",
            "test_scoped_chat_stream_emits_empty_sources_trailer",
        ],
    )


def test_knowledge_base_scope_build_tests_are_split_from_scoping_file():
    project_tests = project_tests_dir()
    scoping_source = read_source(project_tests / "test_knowledge_base_scoping.py")
    scope_build_test = project_tests / "test_knowledge_base_scope_build.py"
    focused_files = [
        project_tests / "test_knowledge_base_scope_resolution.py",
        project_tests / "test_knowledge_base_scope_options.py",
        project_tests / "test_knowledge_base_build_requests.py",
        project_tests / "test_knowledge_base_build_status.py",
    ]

    assert scope_build_test.exists()
    for focused_file in focused_files:
        assert focused_file.exists()
    assert_test_names_moved(
        mixed_source=scoping_source,
        focused_source=combined_source(focused_files),
        test_names=[
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
        ],
    )


def test_knowledge_base_scope_build_tests_are_split_by_domain():
    project_tests = project_tests_dir()
    mixed_test = project_tests / "test_knowledge_base_scope_build.py"

    assert_focused_files_contain_tests(
        mixed_source=read_optional_source(mixed_test),
        focused_dir=project_tests,
        focused_files={
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
        },
    )

    if mixed_test.exists():
        assert len(read_source(mixed_test).splitlines()) <= 80


def test_knowledge_scope_tests_are_split_by_domain():
    project_tests = project_tests_dir()
    mixed_test = project_tests / "test_knowledge_scope.py"

    assert_focused_files_contain_tests(
        mixed_source=read_optional_source(mixed_test),
        focused_dir=project_tests / "knowledge_scope",
        focused_files={
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
        },
    )

    if mixed_test.exists():
        assert len(read_source(mixed_test).splitlines()) <= 80
