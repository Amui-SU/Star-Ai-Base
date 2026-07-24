from types import SimpleNamespace

from langchain.schema import Document

from app.services.chat_routing import (
    extract_keywords,
    filter_docs_by_keywords,
    route_with_llm,
    route_with_rules,
)


def test_route_with_rules_prefers_direct_for_plain_greeting():
    assert (
        route_with_rules("你好", is_collection_intent=False, related=False) == "direct"
    )


def test_route_with_rules_prefers_list_and_summary_intents():
    assert (
        route_with_rules("收藏夹里有哪些视频", is_collection_intent=True, related=False)
        == "db_list"
    )
    assert (
        route_with_rules("总结一下收藏夹内容", is_collection_intent=True, related=False)
        == "db_content"
    )


def test_extract_keywords_removes_stopwords_and_preserves_ascii_terms():
    assert extract_keywords("请问 RAG 视频讲了什么") == ["视频讲了什么", "RAG"]


def test_filter_docs_by_keywords_matches_title_or_content():
    matched_by_title = Document(
        page_content="unrelated", metadata={"title": "RAG 入门教程"}
    )
    matched_by_content = Document(page_content="这里讲到了向量检索", metadata={})
    unmatched = Document(page_content="普通内容", metadata={"title": "其他"})

    assert filter_docs_by_keywords(
        [matched_by_title, unmatched],
        "RAG 是什么",
    ) == [matched_by_title]
    assert filter_docs_by_keywords(
        [matched_by_content, unmatched],
        "向量检索",
    ) == [matched_by_content]


def test_route_with_llm_uses_injected_dependencies_and_parses_route():
    calls = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls["kwargs"] = kwargs
            message = SimpleNamespace(content="vector")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    route, raw = route_with_llm(
        "中西方文化的差异是什么",
        resolve_llm_config=lambda: {
            "model": "fake-model",
            "advanced_config": {
                "user_agent": "Router/1.0",
                "body": {"temperature": 0.3},
            },
        },
        get_llm_client=lambda config: client,
    )

    assert route == "vector"
    assert raw == "vector"
    assert calls["kwargs"]["model"] == "fake-model"
    assert calls["kwargs"]["extra_headers"] == {"User-Agent": "Router/1.0"}
    assert calls["kwargs"]["extra_body"] == {"temperature": 0.3}


def test_route_with_llm_returns_empty_route_and_logs_warning_on_failure():
    warnings = []

    route, raw = route_with_llm(
        "测试",
        resolve_llm_config=lambda: {"model": "fake-model"},
        get_llm_client=lambda config: (_ for _ in ()).throw(RuntimeError("boom")),
        log_warning=warnings.append,
    )

    assert route is None
    assert raw == ""
    assert warnings and "LLM 路由失败" in warnings[0]
