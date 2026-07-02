from .helpers import get_project_root


def test_chat_streaming_uses_state_helpers():
    project_root = get_project_root()
    hook_file = (
        project_root / "frontend" / "components" / "chat" / "useChatStreaming.ts"
    )
    state_helper = (
        project_root / "frontend" / "components" / "chat" / "chatStreamingState.ts"
    )
    runtime_helper = (
        project_root / "frontend" / "components" / "chat" / "chatStreamingRuntime.ts"
    )

    assert state_helper.exists()
    assert runtime_helper.exists()
    hook_source = hook_file.read_text(encoding="utf-8")
    helper_source = state_helper.read_text(encoding="utf-8")
    runtime_source = runtime_helper.read_text(encoding="utf-8")

    for helper_name in [
        "extractThinkingFromContent",
        "updateAssistantMessage",
        "startAssistantStreaming",
        "applyParsedStreamUpdate",
        "finalizeStreamedAssistantAnswer",
        "finalizeFallbackAssistantAnswer",
        "applyAssistantError",
        "resetAssistantForRegeneration",
    ]:
        assert f"export function {helper_name}" in helper_source

    for helper_name in [
        "updateAssistantMessage",
        "startAssistantStreaming",
        "applyParsedStreamUpdate",
        "finalizeStreamedAssistantAnswer",
        "finalizeFallbackAssistantAnswer",
        "applyAssistantError",
        "resetAssistantForRegeneration",
    ]:
        assert helper_name in hook_source

    assert "extractThinkingFromContent" in runtime_source
    assert 'from "@/components/chat/chatStreamingState"' in hook_source
    assert "function extractThinkingFromContent" not in hook_source
    assert "interface ThinkingExtraction" not in hook_source
    assert "prev.map((m)" not in hook_source
    assert "prev.map((message)" not in hook_source


def test_chat_streaming_uses_runtime_helper():
    project_root = get_project_root()
    hook_file = (
        project_root / "frontend" / "components" / "chat" / "useChatStreaming.ts"
    )
    runtime_helper = (
        project_root / "frontend" / "components" / "chat" / "chatStreamingRuntime.ts"
    )

    assert runtime_helper.exists()
    hook_source = hook_file.read_text(encoding="utf-8")
    runtime_source = runtime_helper.read_text(encoding="utf-8")

    assert 'from "@/components/chat/chatStreamingRuntime"' in hook_source
    assert "streamKnowledgeBaseAnswer" in hook_source
    assert "export function streamKnowledgeBaseAnswer" in runtime_source

    for token in [
        "CHAT_STREAM_IDLE_TIMEOUT_MS",
        "knowledgeBaseApi.chatStreamUrl",
        "knowledgeBaseApi.chat(",
        "fetch(",
        "response.body.getReader",
        "new TextDecoder",
        "parseChatStream",
        "new AbortController",
    ]:
        assert token not in hook_source
        assert token in runtime_source
