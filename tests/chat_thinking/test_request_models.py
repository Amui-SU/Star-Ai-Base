from app.models import ChatRequest, KnowledgeBaseChatRequest


def test_chat_request_models_no_longer_expose_request_mode_switches():
    assert "smart_search" not in ChatRequest.model_fields
    assert "smart_search" not in KnowledgeBaseChatRequest.model_fields
    assert "deep_think" not in ChatRequest.model_fields
    assert "deep_think" not in KnowledgeBaseChatRequest.model_fields


def test_knowledge_base_chat_request_supports_web_search_toggle():
    assert KnowledgeBaseChatRequest(question="hello").web_search is False
    assert (
        KnowledgeBaseChatRequest(question="hello", web_search=True).web_search is True
    )


def test_knowledge_base_chat_request_supports_web_search_provider():
    assert KnowledgeBaseChatRequest(question="hello").web_search_provider == "auto"
    assert (
        KnowledgeBaseChatRequest(
            question="hello",
            web_search=True,
            web_search_provider="Tavily",
        ).web_search_provider
        == "tavily"
    )
