import asyncio
import json

import pytest

from tests.test_knowledge_base_scoping import create_knowledge_base, register_user


@pytest.mark.asyncio
async def test_scoped_chat_stream_reports_web_search_no_results(client, monkeypatch):
    await register_user(client, "web-stream-empty@example.com", "Web Stream Empty")
    knowledge_base = await create_knowledge_base(client, "Web Stream Empty KB")

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Stream answer chunk.",
                        "metadata": {
                            "bvid": "BV1KB",
                            "title": "Knowledge Source",
                        },
                    },
                )()
            ]

    class FakeToolFunction:
        name = "web_search"
        arguments = json.dumps({"query": "模型搜索词"}, ensure_ascii=False)

    class FakeToolCall:
        id = "call_empty_search"
        function = FakeToolFunction()

    class FakeToolMessage:
        content = ""
        reasoning_content = ""
        tool_calls = [FakeToolCall()]

        def model_dump(self, exclude_none=True):
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_empty_search",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ],
            }

    class FakeCompletions:
        def create(self, **kwargs):
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": FakeToolMessage()})()]},
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def empty_search_web(*args, **kwargs):
        return []

    def fake_stream_llm_events(messages):
        yield "answer", "模型答案"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "test",
            "model": "tool-model",
            "api_key": "test",
            "base_url": "https://example.com",
            "thinking_config": {},
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._resolve_llm_config",
        lambda: {"thinking_config": {}},
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", empty_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "查外部资料", "web_search": True},
    )

    assert response.status_code == 200
    assert "[[WEB_SEARCH_JSON]]" in response.text
    assert '"status": "no_results"' in response.text
    assert '"queries": ["查外部资料", "模型搜索词"]' in response.text
    assert '"results": []' in response.text
    assert "联网搜索未找到可用结果，已仅参考知识库" in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_reports_socks_dependency_failure(client, monkeypatch):
    await register_user(
        client, "web-stream-socks-failure@example.com", "Web Stream Socks Failure"
    )
    knowledge_base = await create_knowledge_base(client, "Web Stream Socks Failure KB")

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Knowledge context.",
                        "metadata": {"bvid": "BV1KB", "title": "Knowledge Source"},
                    },
                )()
            ]

    async def failing_prepare(*args, **kwargs):
        raise RuntimeError(
            "Using SOCKS proxy, but the 'socksio' package is not installed. "
            "Make sure to install httpx using `pip install httpx[socks]`."
        )

    def fake_stream_llm_events(messages):
        yield "answer", "模型答案"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_knowledge_base_web_search",
        failing_prepare,
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
    assert "[[WEB_SEARCH_JSON]]" in response.text
    assert '"status": "failed"' in response.text
    assert "联网搜索代理依赖缺失" in response.text
    assert "当前模型不支持联网搜索工具调用" not in response.text
    assert '"source": "web_search"' in response.text
    assert "socksio" in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_emits_web_search_progress_before_tool_setup(
    client, monkeypatch
):
    await register_user(
        client, "web-stream-progress@example.com", "Web Stream Progress"
    )
    knowledge_base = await create_knowledge_base(client, "Web Stream Progress KB")

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return []

    async def fake_prepare_knowledge_base_web_search(messages, *, question):
        from app.routers.chat import LLMToolRunResult

        return (
            LLMToolRunResult(
                messages=[
                    *messages,
                    {"role": "system", "content": "web context"},
                ],
            ),
            [
                {
                    "title": "Web Source",
                    "url": "https://example.com/web",
                    "snippet": "snippet",
                }
            ],
            {
                "status": "success",
                "message": "已使用联网搜索",
                "result_count": 1,
            },
        )

    def fake_stream_llm_events(messages):
        yield "thinking", "模型思考"
        yield "answer", "模型答案"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_knowledge_base_web_search",
        fake_prepare_knowledge_base_web_search,
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
    first_model_thinking = '[[THINKING_DELTA]]"模型思考"'
    assert first_progress in response.text
    assert first_model_thinking in response.text
    assert response.text.index(first_progress) < response.text.index(
        first_model_thinking
    )
    assert '[[THINKING_JSON]]"模型思考"' in response.text
    assert "正在联网搜索外部资料。模型思考" not in response.text


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
        from app.routers.chat import LLMToolRunResult

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
            _collect_web_search_heartbeat_events(generator, events),
            timeout=0.2,
        )

    assert events
    assert events[0][0] == "heartbeat"


async def _collect_web_search_heartbeat_events(generator, events):
    async for event in generator:
        events.append(event)


def test_web_search_tool_prep_timeout_allows_slow_model_tool_planning():
    from app.routers import knowledge_bases

    assert knowledge_bases.WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS >= 60.0


@pytest.mark.asyncio
async def test_scoped_chat_stream_adds_web_sources_from_initial_search(
    client, monkeypatch
):
    await register_user(
        client, "web-stream-fallback@example.com", "Web Stream Fallback"
    )
    knowledge_base = await create_knowledge_base(client, "Web Stream Fallback KB")
    captured = {"queries": [], "stream_messages": []}

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Knowledge context.",
                        "metadata": {"bvid": "BV1KB", "title": "Knowledge Source"},
                    },
                )()
            ]

    class FakeToolFunction:
        name = "web_search"
        arguments = json.dumps({"query": "model query with no hits"})

    class FakeToolCall:
        id = "call_empty_search"
        function = FakeToolFunction()

    class FakeToolMessage:
        content = ""
        reasoning_content = ""
        tool_calls = [FakeToolCall()]

        def model_dump(self, exclude_none=True):
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_empty_search",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ],
            }

    class FakeCompletions:
        def create(self, **kwargs):
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": FakeToolMessage()})()]},
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_search_web(query, *, max_results=3):
        captured["queries"].append(query)
        if query == "original user question":
            return [
                {
                    "title": "Direct Fallback Web",
                    "url": "https://example.com/direct-fallback",
                    "snippet": "Direct fallback snippet",
                }
            ]
        return []

    def fake_stream_llm_events(messages):
        captured["stream_messages"].append(messages)
        assert "Direct Fallback Web" in json.dumps(messages, ensure_ascii=False)
        yield "answer", "stream answer with fallback web"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "test",
            "model": "tool-model",
            "api_key": "test",
            "base_url": "https://example.com",
            "thinking_config": {},
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._resolve_llm_config",
        lambda: {"thinking_config": {}},
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "original user question", "web_search": True},
    )

    assert response.status_code == 200
    assert captured["queries"] == ["original user question", "model query with no hits"]
    assert '"status": "success"' in response.text
    assert '"type": "web"' in response.text
    assert "Direct Fallback Web" in response.text
    assert "https://example.com/direct-fallback" in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_uses_final_stream_after_tool_decision(
    client, monkeypatch
):
    await register_user(client, "web-stream-unused@example.com", "Web Stream Unused")
    knowledge_base = await create_knowledge_base(client, "Web Stream Unused KB")

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "知识库资料",
                        "metadata": {"bvid": "BV1KB", "title": "Knowledge Source"},
                    },
                )()
            ]

    class FakeMessage:
        content = "无需联网的流式答案"
        reasoning_content = "先判断无需搜索"
        tool_calls = None

    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["tools"][0]["function"]["name"] == "web_search"
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": FakeMessage()})()]},
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    captured = {"stream_messages": None}

    def fake_stream_llm_events(messages):
        captured["stream_messages"] = messages
        yield "thinking", "实时思考"
        yield "answer", "实时流式答案"

    async def empty_search_web(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "test",
            "model": "tool-model",
            "api_key": "test",
            "base_url": "https://example.com",
            "thinking_config": {},
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._resolve_llm_config",
        lambda: {"thinking_config": {}},
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", empty_search_web)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "查外部资料", "web_search": True},
    )

    assert response.status_code == 200
    assert "实时流式答案" in response.text
    assert '[[THINKING_DELTA]]"实时思考"' in response.text
    assert "无需联网的流式答案" not in response.text
    assert captured["stream_messages"] is not None
    assert "[[WEB_SEARCH_JSON]]" in response.text
    assert '"status": "no_results"' in response.text
