from .helpers import get_project_root


def test_chat_panel_history_tests_are_split_from_main_suite():
    project_root = get_project_root()
    main_test = project_root / "frontend" / "components" / "ChatPanel.test.tsx"
    history_test = (
        project_root / "frontend" / "components" / "ChatPanel.history.test.tsx"
    )
    test_utils = (
        project_root / "frontend" / "components" / "chat" / "chatPanelTestUtils.tsx"
    )

    main_source = main_test.read_text(encoding="utf-8")

    assert history_test.exists()
    assert test_utils.exists()
    assert (
        "opens a requested conversation from the expanded history panel"
        not in main_source
    )
    assert (
        "starts a new conversation from an expanded-page request without deleting saved history"
        not in main_source
    )

    history_source = history_test.read_text(encoding="utf-8")
    assert (
        "opens a requested conversation from the expanded history panel"
        in history_source
    )
    assert (
        "starts a new conversation from an expanded-page request without deleting saved history"
        in history_source
    )
    assert "@/components/chat/chatPanelTestUtils" in main_source
    assert "@/components/chat/chatPanelTestUtils" in history_source


def test_chat_panel_streaming_tests_are_split_from_main_suite():
    project_root = get_project_root()
    main_test = project_root / "frontend" / "components" / "ChatPanel.test.tsx"
    streaming_test = (
        project_root / "frontend" / "components" / "ChatPanel.streaming.test.tsx"
    )

    moved_tests = [
        "keeps a streaming response alive after the old fixed deadline when content arrived",
        "uses instant autoscroll during streaming updates to avoid repeated smooth-scroll jank",
        "does not force autoscroll while the user reads earlier content during streaming",
        "does not call the non-stream fallback after idle timeout when partial content exists",
    ]
    main_source = main_test.read_text(encoding="utf-8")

    assert streaming_test.exists()
    streaming_source = streaming_test.read_text(encoding="utf-8")
    assert "@/components/chat/chatPanelTestUtils" in streaming_source

    for test_name in moved_tests:
        assert test_name not in main_source
        assert test_name in streaming_source


def test_chat_panel_web_search_tests_are_split_from_main_suite():
    project_root = get_project_root()
    main_test = project_root / "frontend" / "components" / "ChatPanel.test.tsx"
    web_search_test = (
        project_root / "frontend" / "components" / "ChatPanel.web-search.test.tsx"
    )

    moved_tests = [
        "sends the web search flag when the picker toggle is enabled",
        "resets the web search provider to auto when enabling search from the picker",
        "opens Tavily config from web search provider choice and sends Tavily after saving",
        "shows the web search notice only on the scope chip and then restores the scope text",
    ]
    main_source = main_test.read_text(encoding="utf-8")

    assert web_search_test.exists()
    web_search_source = web_search_test.read_text(encoding="utf-8")
    assert "@/components/chat/chatPanelTestUtils" in web_search_source

    for test_name in moved_tests:
        assert test_name not in main_source
        assert test_name in web_search_source


def test_chat_panel_web_search_result_tests_are_split_from_toggle_suite():
    project_root = get_project_root()
    web_search_test = (
        project_root / "frontend" / "components" / "ChatPanel.web-search.test.tsx"
    )
    results_test = (
        project_root
        / "frontend"
        / "components"
        / "ChatPanel.web-search-results.test.tsx"
    )
    focused_dir = project_root / "frontend" / "components" / "chat" / "__tests__"
    focused_files = [
        focused_dir / "ChatPanel.web-search-sources.test.tsx",
        focused_dir / "ChatPanel.web-search-progress.test.tsx",
        focused_dir / "ChatPanel.web-search-status.test.tsx",
    ]

    moved_tests = [
        "labels knowledge and web sources in assistant references",
        "shows web sources from the streaming metadata in assistant references",
        "renders web search progress as a live status outside thinking text",
        "clears previous references immediately when regenerating an answer",
        "shows web search fallback status returned by the chat response",
        "shows attempted queries when web search returns no results",
    ]
    web_search_source = web_search_test.read_text(encoding="utf-8")

    assert results_test.exists()
    for focused_file in focused_files:
        assert focused_file.exists()
    focused_source = "\n".join(
        focused_file.read_text(encoding="utf-8") for focused_file in focused_files
    )
    assert "@/components/chat/chatPanelTestUtils" in focused_source

    for test_name in moved_tests:
        assert test_name not in web_search_source
        assert test_name in focused_source


def test_chat_panel_config_tests_are_split_from_main_suite():
    project_root = get_project_root()
    main_test = project_root / "frontend" / "components" / "ChatPanel.test.tsx"
    config_test = project_root / "frontend" / "components" / "ChatPanel.config.test.tsx"

    moved_tests = [
        "does not show the AI key prompt when a model is available",
        "lets users switch between official and personal model sources above the provider list",
        "treats legacy model config without an explicit source as official",
        "shows the AI key prompt only after config loads with no usable model",
        "places the knowledge-base meta next to the model selector",
        "hides global provider and Tavily configuration controls from regular users",
        "lets regular users open their own AI service key settings for Tavily",
    ]
    main_source = main_test.read_text(encoding="utf-8")

    assert config_test.exists()
    config_source = config_test.read_text(encoding="utf-8")
    assert "@/components/chat/chatPanelTestUtils" in config_source

    for test_name in moved_tests:
        assert test_name not in main_source
        assert test_name in config_source
