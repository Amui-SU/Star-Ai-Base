from .helpers import get_project_root


def test_message_list_uses_focused_subcomponents():
    project_root = get_project_root()
    message_list = (
        project_root / "frontend" / "components" / "chat" / "MessageList.tsx"
    ).read_text(encoding="utf-8")

    for relative_path in [
        "frontend/components/chat/MessageSources.tsx",
        "frontend/components/chat/MessageActions.tsx",
    ]:
        assert (project_root / relative_path).exists()

    assert "@/components/chat/MessageSources" in message_list
    assert "@/components/chat/MessageActions" in message_list
    assert "function CopyIcon" not in message_list
    assert "source-details" not in message_list
    assert "web-search-error-list" not in message_list
    assert 'aria-label="回答操作"' not in message_list
    assert 'aria-label="问题操作"' not in message_list


def test_chat_scope_picker_uses_focused_subcomponents():
    project_root = get_project_root()
    picker = (
        project_root / "frontend" / "components" / "ChatScopePicker.tsx"
    ).read_text(encoding="utf-8")

    for relative_path in [
        "frontend/components/chat-scope/ChatScopeTrigger.tsx",
        "frontend/components/chat-scope/ScopeWebSearchPanel.tsx",
        "frontend/components/chat-scope/ScopeModeGrid.tsx",
        "frontend/components/chat-scope/ScopeFolderSection.tsx",
        "frontend/components/chat-scope/ScopeVideoSearchSection.tsx",
    ]:
        assert (project_root / relative_path).exists()

    for import_path in [
        "@/components/chat-scope/ChatScopeTrigger",
        "@/components/chat-scope/ScopeWebSearchPanel",
        "@/components/chat-scope/ScopeModeGrid",
        "@/components/chat-scope/ScopeFolderSection",
        "@/components/chat-scope/ScopeVideoSearchSection",
    ]:
        assert import_path in picker

    for token in [
        "scope-web-provider-panel",
        "scope-mode-grid",
        "scope-folder-row",
        "scope-video-list",
        "scope-web-search-privacy",
    ]:
        assert token not in picker
