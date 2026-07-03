from .helpers import get_project_root


def test_chat_panel_uses_chat_subcomponents():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    view_file = project_root / "frontend" / "components" / "chat" / "ChatPanelView.tsx"
    composer_section = (
        project_root
        / "frontend"
        / "components"
        / "chat"
        / "ChatPanelComposerSection.tsx"
    ).read_text(encoding="utf-8")

    for relative_path in [
        "frontend/components/chat/MessageList.tsx",
        "frontend/components/chat/Composer.tsx",
        "frontend/components/chat/ChatPanelComposerSection.tsx",
        "frontend/components/chat/ChatPanelView.tsx",
        "frontend/components/chat/WebSearchConfigModal.tsx",
        "frontend/components/chat/ModelConfigModal.tsx",
        "frontend/components/chat/useChatStreaming.ts",
        "frontend/components/chat/ChatEmptyState.tsx",
    ]:
        assert (project_root / relative_path).exists()

    view_source = view_file.read_text(encoding="utf-8")
    assert "@/components/chat/ChatPanelView" in chat_panel
    assert "@/components/chat/MessageList" not in chat_panel
    assert "@/components/chat/ChatPanelComposerSection" not in chat_panel
    assert "@/components/chat/MessageList" in view_source
    assert "@/components/chat/ChatPanelComposerSection" in view_source
    assert "@/components/chat/Composer" not in chat_panel
    assert "@/components/chat/Composer" in composer_section
    assert "@/components/chat/WebSearchConfigModal" not in chat_panel
    assert "@/components/chat/ModelConfigModal" not in chat_panel
    assert "@/components/chat/WebSearchConfigModal" in view_source
    assert "@/components/chat/ModelConfigModal" in view_source
    assert "@/components/chat/useChatStreaming" in chat_panel
    assert "@/components/chat/ChatEmptyState" not in chat_panel
    assert "@/components/chat/ChatEmptyState" in view_source
    assert "provider-config-body" not in chat_panel
    assert "thinking-config-fieldset" not in chat_panel
    assert "鎺㈢储浣犵殑鏀惰棌" not in chat_panel
    assert "鎬荤粨鏀惰棌澶归噷鏈€鏈変环鍊肩殑鍐呭" not in chat_panel


def test_chat_panel_model_status_menu_is_extracted():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    view_source = (
        project_root / "frontend" / "components" / "chat" / "ChatPanelView.tsx"
    ).read_text(encoding="utf-8")
    header_component = (
        project_root / "frontend" / "components" / "chat" / "ChatPanelHeader.tsx"
    ).read_text(encoding="utf-8")
    status_component = (
        project_root / "frontend" / "components" / "chat" / "ChatModelStatus.tsx"
    )

    assert status_component.exists()
    assert "@/components/chat/ChatPanelHeader" not in chat_panel
    assert "@/components/chat/ChatPanelHeader" in view_source
    assert "@/components/chat/ChatModelStatus" not in chat_panel
    assert "@/components/chat/ChatModelStatus" in header_component
    assert 'from "next/image"' not in chat_panel
    assert "@/lib/providers" not in chat_panel
    assert "modelMenuRef" not in chat_panel
    assert "model-provider-menu" not in chat_panel
    assert "model-source-switch" not in chat_panel


def test_chat_panel_uses_header_section_component():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    view_source = (
        project_root / "frontend" / "components" / "chat" / "ChatPanelView.tsx"
    ).read_text(encoding="utf-8")
    header_file = (
        project_root / "frontend" / "components" / "chat" / "ChatPanelHeader.tsx"
    )

    assert header_file.exists()
    header_source = header_file.read_text(encoding="utf-8")
    assert "export default function ChatPanelHeader" in header_source
    assert "@/components/chat/ChatPanelHeader" not in chat_panel
    assert "@/components/chat/ChatPanelHeader" in view_source
    assert "@/components/chat/ChatModelStatus" not in chat_panel
    assert "@/components/chat/ChatModelStatus" in header_source
    assert "chat-context-row" not in chat_panel
    assert "chat-context-actions" not in chat_panel
    assert "chat-kb-context" not in chat_panel
    assert "chat-kb-meta" not in chat_panel


def test_chat_panel_uses_composer_section_component():
    project_root = get_project_root()
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    view_source = (
        project_root / "frontend" / "components" / "chat" / "ChatPanelView.tsx"
    ).read_text(encoding="utf-8")
    section_file = (
        project_root
        / "frontend"
        / "components"
        / "chat"
        / "ChatPanelComposerSection.tsx"
    )

    assert section_file.exists()
    section_source = section_file.read_text(encoding="utf-8")
    assert "export default function ChatPanelComposerSection" in section_source
    assert "@/components/chat/ChatPanelComposerSection" not in chat_panel
    assert "@/components/chat/ChatPanelComposerSection" in view_source
    assert "panel-footer border-transparent" not in chat_panel
    assert "scope-notice" not in chat_panel
    assert "composer-disclaimer" not in chat_panel
    assert "<Composer" not in chat_panel


def test_frontend_provider_presets_are_shared():
    project_root = get_project_root()
    providers_file = project_root / "frontend" / "lib" / "providers.ts"
    chat_panel = (project_root / "frontend" / "components" / "ChatPanel.tsx").read_text(
        encoding="utf-8"
    )
    view_source = (
        project_root / "frontend" / "components" / "chat" / "ChatPanelView.tsx"
    ).read_text(encoding="utf-8")
    chat_panel_header = (
        project_root / "frontend" / "components" / "chat" / "ChatPanelHeader.tsx"
    ).read_text(encoding="utf-8")
    chat_model_status = (
        project_root / "frontend" / "components" / "chat" / "ChatModelStatus.tsx"
    ).read_text(encoding="utf-8")
    api_account_form = (
        project_root / "frontend" / "components" / "api-accounts" / "ApiAccountForm.tsx"
    ).read_text(encoding="utf-8")

    assert providers_file.exists()
    assert "@/components/chat/ChatPanelView" in chat_panel
    assert "@/components/chat/ChatPanelHeader" not in chat_panel
    assert "@/components/chat/ChatPanelHeader" in view_source
    assert "@/components/chat/ChatModelStatus" in chat_panel_header
    assert "@/lib/providers" in chat_model_status
    assert "@/lib/providers" in api_account_form
    assert "const PROVIDERS" not in api_account_form
    assert "const builtInProviders" not in chat_panel
    assert "const providerLogoMap" not in chat_panel
