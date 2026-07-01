import asyncio

import pytest

from tests.knowledge_base_web_search_streaming.helpers import (
    collect_web_search_heartbeat_events,
)
from tests.test_knowledge_base_scoping import create_knowledge_base
from tests.test_knowledge_base_scoping import register_user


@pytest.mark.asyncio
async def test_scoped_chat_stream_emits_web_search_heartbeat_while_preparing(
    client, monkeypatch
):
    await register_user(client, "web-stream-heartbeat@example.com", "Web Heartbeat")
    knowledge_base = await create_knowledge_base(client, "Web Heartbeat KB")

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return []

    async def slow_prepare_knowledge_base_web_search(messages, *, question):
        from app.services.llm_tool_calls import LLMToolRunResult

        await asyncio.sleep(0.05)
        return (
            LLMToolRunResult(messages=messages),
            [],
            {
                "status": "no_results",
                "message": "联网搜索未找到可用结果，已仅参考知识库",
                "result_count": 0,
                "queries": [question],
                "results": [],
            },
        )

    def fake_stream_llm_events(messages):
        yield "answer", "模型答案"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS",
        0.01,
        raising=False,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_knowledge_base_web_search",
        slow_prepare_knowledge_base_web_search,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "查外部资料", "web_search": True},
    )

    assert response.status_code == 200
    first_progress = '[[WEB_SEARCH_PROGRESS]]"正在联网搜索外部资料"'
    assert first_progress in response.text
    heartbeat = '[[WEB_SEARCH_PROGRESS]]"联网搜索仍在进行'
    assert heartbeat in response.text
    assert response.text.index(heartbeat) < response.text.index("模型答案")
    assert '[[WEB_SEARCH_PROGRESS]]""' in response.text
    assert '[[THINKING_DELTA]]"联网搜索仍在进行' not in response.text
    assert '[[THINKING_JSON]]"联网搜索仍在进行' not in response.text


@pytest.mark.asyncio
async def test_web_search_heartbeat_generator_cancels_prepare_task_on_close(
    monkeypatch,
):
    from app.routers import knowledge_bases

    captured = {"cancelled": False}

    async def never_finishing_prepare(messages, *, question):
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            captured["cancelled"] = True
            raise

    monkeypatch.setattr(
        "app.routers.knowledge_bases.WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS",
        0.01,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_knowledge_base_web_search",
        never_finishing_prepare,
    )

    generator = knowledge_bases._prepare_knowledge_base_web_search_with_heartbeats(
        [{"role": "user", "content": "question"}],
        question="question",
    )
    event_type, _event_payload = await generator.__anext__()
    assert event_type == "heartbeat"

    await generator.aclose()

    assert captured["cancelled"] is True


@pytest.mark.asyncio
async def test_web_search_heartbeat_generator_times_out_tool_setup(monkeypatch):
    from app.routers import knowledge_bases

    async def never_finishing_prepare(messages, *, question):
        await asyncio.sleep(60)

    monkeypatch.setattr(
        "app.routers.knowledge_bases.WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS",
        0.01,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS",
        0.025,
        raising=False,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_knowledge_base_web_search",
        never_finishing_prepare,
    )

    generator = knowledge_bases._prepare_knowledge_base_web_search_with_heartbeats(
        [{"role": "user", "content": "question"}],
        question="question",
    )
    events = []
    with pytest.raises(TimeoutError, match="web search tool chain timed out"):
        await asyncio.wait_for(
            collect_web_search_heartbeat_events(generator, events),
            timeout=0.2,
        )

    assert events
    assert events[0][0] == "heartbeat"


def test_web_search_tool_prep_timeout_allows_slow_model_tool_planning():
    from app.routers import knowledge_bases

    assert knowledge_bases.WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS >= 60.0
