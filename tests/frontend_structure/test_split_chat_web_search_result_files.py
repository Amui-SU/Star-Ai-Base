from .helpers import get_project_root


def test_chat_panel_web_search_result_tests_are_split_by_domain():
    project_root = get_project_root()
    components_dir = project_root / "frontend" / "components"
    original_file = components_dir / "ChatPanel.web-search-results.test.tsx"
    focused_dir = components_dir / "chat" / "__tests__"

    focused_files = {
        "ChatPanel.web-search-sources.test.tsx": [
            "labels knowledge and web sources in assistant references",
            "shows web sources from the streaming metadata in assistant references",
            "clears previous references immediately when regenerating an answer",
        ],
        "ChatPanel.web-search-progress.test.tsx": [
            "renders web search progress as a live status outside thinking text",
        ],
        "ChatPanel.web-search-status.test.tsx": [
            "shows web search fallback status returned by the chat response",
            "shows attempted queries when web search returns no results",
        ],
    }

    original_source = original_file.read_text(encoding="utf-8")
    for file_name, test_names in focused_files.items():
        focused_path = focused_dir / file_name
        assert focused_path.exists()
        focused_source = focused_path.read_text(encoding="utf-8")
        for test_name in test_names:
            assert test_name not in original_source
            assert test_name in focused_source

    assert original_source.count("it(") <= 1
