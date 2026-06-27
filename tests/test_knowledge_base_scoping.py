import asyncio
import json
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    SourceBinding,
    SourceCredential,
    SystemSession,
    VideoCache,
)
from app.security import encrypt_text


async def _get_code(client, email: str) -> str:
    resp = await client.post("/system-auth/send-code", json={"email": email})
    assert resp.status_code == 200
    return resp.json()["code"]


async def register_user(client, email: str, display_name: str) -> dict:
    code = await _get_code(client, email)
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": display_name,
            "code": code,
        },
    )
    assert response.status_code == 200
    auth = response.json()
    account_response = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "api_key": "test-user-api-key",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "is_default": True,
        },
        headers={"Authorization": f"Bearer {auth['session_token']}"},
    )
    assert account_response.status_code == 200
    return auth


async def create_knowledge_base(client, name: str = "Scoped KB") -> dict:
    response = await client.post(
        "/knowledge-bases",
        json={"name": name, "description": "scope test"},
    )
    assert response.status_code == 200
    return response.json()


async def create_source_binding(
    db_session_factory,
    *,
    user_id: int,
    workspace_id: int,
    status: str = "active",
) -> SourceBinding:
    async with db_session_factory() as session:
        binding = SourceBinding(
            user_id=user_id,
            workspace_id=workspace_id,
            source_type="bilibili",
            external_account_id=f"mid-{user_id}-{workspace_id}-{status}",
            external_account_name="Bilibili Account",
            status=status,
        )
        session.add(binding)
        await session.flush()
        session.add(
            SourceCredential(
                user_id=user_id,
                source_binding_id=binding.id,
                encrypted_payload=encrypt_text(
                    json.dumps(
                        {
                            "SESSDATA": "test-session",
                            "bili_jct": "test-csrf",
                            "DedeUserID": str(user_id),
                        }
                    )
                ),
            )
        )
        await session.commit()
        await session.refresh(binding)
        return binding


async def seed_scope_folder(
    db_session_factory,
    *,
    knowledge_base: dict,
    media_id: int,
    title: str,
    videos: list[tuple[str, str]],
) -> None:
    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id=f"scope-{knowledge_base['id']}-{media_id}",
            workspace_id=knowledge_base["workspace_id"],
            knowledge_base_id=knowledge_base["id"],
            media_id=media_id,
            title=title,
            last_sync_at=datetime(2026, 6, 14),
            updated_at=datetime(2026, 6, 14),
        )
        session.add(folder)
        await session.flush()
        for bvid, video_title in videos:
            session.add(
                FavoriteVideo(
                    folder_id=folder.id,
                    bvid=bvid,
                    workspace_id=knowledge_base["workspace_id"],
                    knowledge_base_id=knowledge_base["id"],
                )
            )
            session.add(
                VideoCache(
                    bvid=bvid,
                    title=video_title,
                    is_processed=True,
                    workspace_id=knowledge_base["workspace_id"],
                    knowledge_base_id=knowledge_base["id"],
                )
            )
        await session.commit()


@pytest.mark.asyncio
async def test_scoped_stats_requires_login(client):
    response = await client.get("/knowledge-bases/1/stats")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scoped_stats_hides_other_users_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.get(f"/knowledge-bases/{alice_kb['id']}/stats")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_search_uses_workspace_and_knowledge_base_filter(
    client,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Search KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["query"] = query
            captured["workspace_id"] = workspace_id
            captured["knowledge_base_id"] = knowledge_base_id
            captured["k"] = k
            captured["bvids"] = bvids
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "chunk text",
                        "metadata": {
                            "bvid": "BV1xx411c7mD",
                            "title": "Test Video",
                            "url": "https://www.bilibili.com/video/BV1xx411c7mD",
                        },
                    },
                )()
            ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/search",
        json={"query": "人工智能", "k": 3},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["title"] == "Test Video"
    assert captured == {
        "query": "人工智能",
        "workspace_id": knowledge_base["workspace_id"],
        "knowledge_base_id": knowledge_base["id"],
        "k": 3,
        "bvids": None,
    }


@pytest.mark.asyncio
async def test_scoped_chat_uses_scoped_retrieval(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Chat KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["query"] = query
            captured["workspace_id"] = workspace_id
            captured["knowledge_base_id"] = knowledge_base_id
            captured["k"] = k
            captured["bvids"] = bvids
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Python is a programming language.",
                        "metadata": {
                            "bvid": "BV1py411c7mD",
                            "title": "Python Intro",
                            "url": "https://www.bilibili.com/video/BV1py411c7mD",
                        },
                    },
                )()
            ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "What is Python?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "Python" in body["answer"]
    assert body["sources"][0]["title"] == "Python Intro"
    assert captured["workspace_id"] == knowledge_base["workspace_id"]
    assert captured["knowledge_base_id"] == knowledge_base["id"]


@pytest.mark.asyncio
async def test_scoped_chat_lets_llm_call_web_search_tool_when_enabled(
    client, monkeypatch
):
    await register_user(client, "web-search@example.com", "Web Search")
    knowledge_base = await create_knowledge_base(client, "Web Search KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "知识库资料",
                        "metadata": {
                            "bvid": "BV1KB",
                            "title": "Knowledge Source",
                            "url": "https://www.bilibili.com/video/BV1KB",
                        },
                    },
                )()
            ]

    async def fake_search_web(query, *, max_results=3):
        captured["query"] = query
        captured["max_results"] = max_results
        return [
            {
                "title": "外部资料标题",
                "url": "https://example.com/news",
                "snippet": "外部资料摘要",
            }
        ]

    async def fake_complete_with_tools(messages, *, question, enable_web_search):
        captured["question"] = question
        captured["enable_web_search"] = enable_web_search
        captured["messages"] = messages
        return (
            "联网答案",
            "",
            [
                {
                    "title": "外部资料标题",
                    "url": "https://example.com/news",
                    "snippet": "外部资料摘要",
                }
            ],
            {
                "status": "success",
                "message": "已使用联网搜索",
                "result_count": 1,
            },
        )

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_knowledge_base_answer",
        fake_complete_with_tools,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "今天有什么新进展？", "web_search": True},
    )

    assert response.status_code == 200
    assert "query" not in captured
    assert captured["enable_web_search"] is True
    assert "外部资料标题" not in str(captured["messages"])
    assert "外部资料摘要" not in str(captured["messages"])
    assert response.json()["sources"][-1] == {
        "type": "web",
        "title": "外部资料标题",
        "url": "https://example.com/news",
    }
    assert response.json()["web_search"]["status"] == "success"
    assert response.json()["web_search"]["message"] == "已使用联网搜索"
    assert response.json()["web_search"]["result_count"] == 1


@pytest.mark.asyncio
async def test_scoped_chat_reports_socks_dependency_failure(client, monkeypatch):
    await register_user(client, "web-socks-failure@example.com", "Web Socks Failure")
    knowledge_base = await create_knowledge_base(client, "Web Socks Failure KB")

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

    async def failing_complete(*args, **kwargs):
        raise RuntimeError(
            "Using SOCKS proxy, but the 'socksio' package is not installed. "
            "Make sure to install httpx using `pip install httpx[socks]`."
        )

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_knowledge_base_answer",
        failing_complete,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "查外部资料", "web_search": True},
    )

    assert response.status_code == 200
    web_search = response.json()["web_search"]
    assert web_search["status"] == "failed"
    assert "联网搜索代理依赖缺失" in web_search["message"]
    assert "当前模型不支持联网搜索工具调用" not in web_search["message"]
    assert web_search["errors"][0]["source"] == "web_search"
    assert "socksio" in web_search["errors"][0]["message"]


@pytest.mark.asyncio
async def test_scoped_chat_web_search_tool_chain_executes_model_requested_query(
    client, monkeypatch
):
    await register_user(client, "web-tool-chain@example.com", "Web Tool Chain")
    knowledge_base = await create_knowledge_base(client, "Web Tool Chain KB")
    captured = {"calls": []}

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

    class FakeToolFunction:
        name = "web_search"
        arguments = json.dumps({"query": "模型改写后的外部查询"}, ensure_ascii=False)

    class FakeToolCall:
        id = "call_search_1"
        function = FakeToolFunction()

    class FakeMessage:
        def __init__(self, *, content="", tool_calls=None):
            self.content = content
            self.reasoning_content = ""
            self.tool_calls = tool_calls

        def model_dump(self, exclude_none=True):
            data = {"role": "assistant", "content": self.content}
            if self.tool_calls is not None:
                data["tool_calls"] = [
                    {
                        "id": "call_search_1",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ]
            return data

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            if len(captured["calls"]) == 1:
                assert kwargs["tools"][0]["function"]["name"] == "web_search"
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(tool_calls=[FakeToolCall()])},
                            )()
                        ]
                    },
                )()
            assert any(message["role"] == "tool" for message in kwargs["messages"])
            assert "搜索结果标题" in json.dumps(kwargs["messages"], ensure_ascii=False)
            if "tools" in kwargs:
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(content="工具链答案")},
                            )()
                        ]
                    },
                )()
            assert "tools" not in kwargs
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="工具链答案")},
                        )()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_search_web(query, *, max_results=3):
        captured["search_query"] = query
        captured["max_results"] = max_results
        return [
            {
                "title": "搜索结果标题",
                "url": "https://example.com/tool",
                "snippet": "搜索结果摘要",
            }
        ]

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

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "今天有什么新进展？", "web_search": True},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "工具链答案"
    assert captured["search_query"] == "模型改写后的外部查询"
    assert captured["max_results"] == 3
    assert len(captured["calls"]) == 2
    assert response.json()["sources"][-1] == {
        "type": "web",
        "title": "搜索结果标题",
        "url": "https://example.com/tool",
    }
    assert response.json()["web_search"]["status"] == "success"
    assert response.json()["web_search"]["message"] == "已使用联网搜索"
    assert response.json()["web_search"]["result_count"] == 1
    assert response.json()["web_search"]["queries"] == [
        "今天有什么新进展？",
        "模型改写后的外部查询",
    ]
    assert response.json()["web_search"]["results"] == [
        {
            "title": "搜索结果标题",
            "url": "https://example.com/tool",
            "snippet": "搜索结果摘要",
        }
    ]


@pytest.mark.asyncio
async def test_scoped_chat_web_search_tool_accepts_query_alias_arguments(
    client, monkeypatch
):
    await register_user(client, "web-tool-alias@example.com", "Web Tool Alias")
    knowledge_base = await create_knowledge_base(client, "Web Tool Alias KB")
    captured = {"calls": []}

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Knowledge content",
                        "metadata": {"bvid": "BV1KB", "title": "Knowledge Source"},
                    },
                )()
            ]

    class FakeToolFunction:
        name = "web_search"
        arguments = {"search_query": "aliased external query"}

    class FakeToolCall:
        id = "call_alias_search"
        function = FakeToolFunction()

    class FakeMessage:
        def __init__(self, *, content="", tool_calls=None):
            self.content = content
            self.reasoning_content = ""
            self.tool_calls = tool_calls

        def model_dump(self, exclude_none=True):
            data = {"role": "assistant", "content": self.content}
            if self.tool_calls is not None:
                data["tool_calls"] = [
                    {
                        "id": "call_alias_search",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ]
            return data

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            if len(captured["calls"]) == 1:
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(tool_calls=[FakeToolCall()])},
                            )()
                        ]
                    },
                )()
            assert "Alias Result" in json.dumps(kwargs["messages"], ensure_ascii=False)
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="alias answer")},
                        )()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_search_web(query, *, max_results=3):
        captured["search_query"] = query
        return [
            {
                "title": "Alias Result",
                "url": "https://example.com/alias",
                "snippet": "Alias snippet",
            }
        ]

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

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "Need external data", "web_search": True},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "alias answer"
    assert captured["search_query"] == "aliased external query"
    assert response.json()["web_search"]["status"] == "success"


@pytest.mark.asyncio
async def test_scoped_chat_tool_chain_can_fetch_selected_web_page(client, monkeypatch):
    await register_user(client, "web-fetch@example.com", "Web Fetch")
    knowledge_base = await create_knowledge_base(client, "Web Fetch KB")
    captured = {"calls": []}

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

    class FakeToolFunction:
        def __init__(self, name: str, arguments: dict):
            self.name = name
            self.arguments = json.dumps(arguments, ensure_ascii=False)

    class FakeToolCall:
        def __init__(self, call_id: str, name: str, arguments: dict):
            self.id = call_id
            self.function = FakeToolFunction(name, arguments)

    class FakeMessage:
        def __init__(self, *, content="", tool_calls=None):
            self.content = content
            self.reasoning_content = ""
            self.tool_calls = tool_calls

        def model_dump(self, exclude_none=True):
            data = {"role": "assistant", "content": self.content}
            if self.tool_calls is not None:
                data["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in self.tool_calls
                ]
            return data

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            call_number = len(captured["calls"])
            if call_number == 1:
                assert {tool["function"]["name"] for tool in kwargs["tools"]} == {
                    "web_search",
                    "fetch_web_page",
                }
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {
                                    "message": FakeMessage(
                                        tool_calls=[
                                            FakeToolCall(
                                                "call_search",
                                                "web_search",
                                                {"query": "外部查询"},
                                            )
                                        ]
                                    )
                                },
                            )()
                        ]
                    },
                )()
            if call_number == 2:
                assert "搜索结果标题" in json.dumps(
                    kwargs["messages"], ensure_ascii=False
                )
                web_search_tool_message = [
                    message
                    for message in kwargs["messages"]
                    if message["role"] == "tool" and message["name"] == "web_search"
                ][-1]
                assert (
                    json.loads(web_search_tool_message["content"])["source_type"]
                    == "web_search"
                )
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {
                                    "message": FakeMessage(
                                        tool_calls=[
                                            FakeToolCall(
                                                "call_fetch",
                                                "fetch_web_page",
                                                {"url": "https://example.com/full"},
                                            )
                                        ]
                                    )
                                },
                            )()
                        ]
                    },
                )()
            assert "网页正文内容" in json.dumps(kwargs["messages"], ensure_ascii=False)
            web_page_tool_message = [
                message
                for message in kwargs["messages"]
                if message["role"] == "tool" and message["name"] == "fetch_web_page"
            ][-1]
            assert (
                json.loads(web_page_tool_message["content"])["source_type"]
                == "web_page"
            )
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="正文增强答案")},
                        )()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_search_web(query, *, max_results=3):
        return [
            {
                "title": "搜索结果标题",
                "url": "https://example.com/full",
                "snippet": "搜索摘要",
            }
        ]

    async def fake_fetch_web_page(url, *, max_chars=4000):
        return {
            "url": url,
            "title": "完整网页",
            "content": "网页正文内容",
        }

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
        "app.routers.knowledge_bases.fetch_web_page",
        fake_fetch_web_page,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "查完整网页", "web_search": True},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "正文增强答案"
    assert response.json()["web_search"]["status"] == "success"
    assert len(captured["calls"]) == 3


@pytest.mark.asyncio
async def test_scoped_chat_direct_fetch_tool_reports_page_source(client, monkeypatch):
    await register_user(client, "web-direct-fetch@example.com", "Web Direct Fetch")
    knowledge_base = await create_knowledge_base(client, "Web Direct Fetch KB")

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

    class FakeToolFunction:
        name = "fetch_web_page"
        arguments = json.dumps(
            {"url": "https://example.com/direct"},
            ensure_ascii=False,
        )

    class FakeToolCall:
        id = "call_direct_fetch"
        function = FakeToolFunction()

    class FakeMessage:
        def __init__(self, *, content="", tool_calls=None):
            self.content = content
            self.reasoning_content = ""
            self.tool_calls = tool_calls

        def model_dump(self, exclude_none=True):
            data = {"role": "assistant", "content": self.content}
            if self.tool_calls is not None:
                data["tool_calls"] = [
                    {
                        "id": "call_direct_fetch",
                        "type": "function",
                        "function": {
                            "name": FakeToolFunction.name,
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ]
            return data

    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(tool_calls=[FakeToolCall()])},
                            )()
                        ]
                    },
                )()
            assert "直接读取的网页正文" in json.dumps(
                kwargs["messages"],
                ensure_ascii=False,
            )
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="直接网页答案")},
                        )()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_fetch_web_page(url, *, max_chars=4000):
        return {
            "url": url,
            "title": "直接网页",
            "content": "直接读取的网页正文",
        }

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
        "app.routers.knowledge_bases.fetch_web_page",
        fake_fetch_web_page,
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", empty_search_web)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={
            "question": "读取这个网页 https://example.com/direct",
            "web_search": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "直接网页答案"
    assert response.json()["sources"][-1] == {
        "type": "web",
        "title": "直接网页",
        "url": "https://example.com/direct",
    }
    assert response.json()["web_search"]["status"] == "success"
    assert response.json()["web_search"]["message"] == "已使用联网搜索"
    assert response.json()["web_search"]["result_count"] == 1
    assert response.json()["web_search"]["queries"] == [
        "读取这个网页 https://example.com/direct"
    ]
    assert response.json()["web_search"]["results"] == [
        {
            "title": "直接网页",
            "url": "https://example.com/direct",
            "snippet": "直接读取的网页正文",
        }
    ]


@pytest.mark.asyncio
async def test_scoped_chat_does_not_web_search_by_default(client, monkeypatch):
    await register_user(client, "no-web-search@example.com", "No Web Search")
    knowledge_base = await create_knowledge_base(client, "No Web Search KB")

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

    async def fail_search_web(*args, **kwargs):
        raise AssertionError("web search should not run when the toggle is off")

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fail_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_llm_answer",
        lambda messages: ("知识库答案", ""),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "只看知识库"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "知识库答案"


@pytest.mark.asyncio
async def test_scoped_chat_forces_web_search_when_enabled_without_model_tool_call(
    client, monkeypatch
):
    await register_user(client, "web-unused@example.com", "Web Unused")
    knowledge_base = await create_knowledge_base(client, "Web Unused KB")
    captured = {"calls": [], "queries": []}

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
        content = "未使用工具的答案"
        reasoning_content = ""
        tool_calls = None

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            assert kwargs["tools"][0]["function"]["name"] == "web_search"
            assert "Forced Web Result" in json.dumps(
                kwargs["messages"],
                ensure_ascii=False,
            )
            assert "Forced snippet" in json.dumps(
                kwargs["messages"],
                ensure_ascii=False,
            )
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

    async def fake_search_web(query, *, max_results=3):
        captured["queries"].append(query)
        return [
            {
                "title": "Forced Web Result",
                "url": "https://example.com/forced",
                "snippet": "Forced snippet",
            }
        ]

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

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "查外部资料", "web_search": True},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "未使用工具的答案"
    assert captured["queries"][0] == "查外部资料"
    assert response.json()["web_search"]["status"] == "success"
    assert response.json()["web_search"]["message"] == "已使用联网搜索"
    assert response.json()["web_search"]["result_count"] == 1
    assert response.json()["web_search"]["queries"] == ["查外部资料"]
    assert response.json()["web_search"]["results"] == [
        {
            "title": "Forced Web Result",
            "url": "https://example.com/forced",
            "snippet": "Forced snippet",
        }
    ]
    assert response.json()["sources"][-1] == {
        "type": "web",
        "title": "Forced Web Result",
        "url": "https://example.com/forced",
    }
    assert len(captured["calls"]) == 1


@pytest.mark.asyncio
async def test_initial_web_context_is_not_duplicated_after_tool_run(monkeypatch):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    captured = {}

    async def fake_search_web(query, *, max_results=3):
        return [
            {
                "title": "Initial Web Result",
                "url": "https://example.com/initial",
                "snippet": "Initial snippet",
            }
        ]

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        captured["messages"] = messages
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    tool_run, web_results, _state = await _prepare_web_search_tool_run(
        [{"role": "user", "content": "知识库资料\n\n问题：question"}],
        question="question",
    )

    assert len(web_results) == 1
    assert (
        json.dumps(captured["messages"], ensure_ascii=False).count("Initial Web Result")
        == 1
    )
    assert (
        json.dumps(tool_run.messages, ensure_ascii=False).count("Initial Web Result")
        == 1
    )


@pytest.mark.asyncio
async def test_initial_web_search_no_results_is_visible_to_model(monkeypatch):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    captured = {}

    async def empty_search_web(*args, **kwargs):
        return []

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        captured["messages"] = messages
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", empty_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    _tool_run, web_results, state = await _prepare_web_search_tool_run(
        [{"role": "user", "content": "知识库资料\n\n问题：question"}],
        question="question",
    )

    serialized_messages = json.dumps(captured["messages"], ensure_ascii=False)
    assert web_results == []
    assert state["attempted"] is True
    assert "初始联网搜索未返回可用结果" in serialized_messages
    assert "不要声称已获得外部网页资料" in serialized_messages
    assert "可以基于模型已有通用知识回答" in serialized_messages
    assert "不要把通用知识伪装成检索资料" in serialized_messages


@pytest.mark.asyncio
async def test_web_search_tool_run_uses_request_provider(monkeypatch):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    captured = {"providers": []}

    async def fake_search_web(query, *, max_results=3, diagnostics=None, provider=None):
        captured["providers"].append(provider)
        return []

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        await kwargs["tool_handlers"]["web_search"]({"query": "tool query"})
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    await _prepare_web_search_tool_run(
        [{"role": "user", "content": "question"}],
        question="initial query",
        provider="tavily",
    )

    assert captured["providers"] == ["tavily", "tavily"]


@pytest.mark.asyncio
async def test_web_search_tool_run_uses_tavily_api_key(monkeypatch):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    captured = {"keys": []}

    async def fake_search_web(
        query,
        *,
        max_results=3,
        diagnostics=None,
        provider=None,
        tavily_api_key=None,
    ):
        captured["keys"].append(tavily_api_key)
        return []

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        await kwargs["tool_handlers"]["web_search"]({"query": "tool query"})
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    await _prepare_web_search_tool_run(
        [{"role": "user", "content": "question"}],
        question="initial query",
        provider="tavily",
        tavily_api_key="user-tavily-key",
    )

    assert captured["keys"] == ["user-tavily-key", "user-tavily-key"]


@pytest.mark.asyncio
async def test_initial_web_search_diagnostics_are_reported_when_search_fails(
    monkeypatch,
):
    from app.routers.knowledge_bases import (
        _prepare_web_search_tool_run,
        _status_from_web_search_state,
    )

    async def failing_search_web(*args, **kwargs):
        kwargs["diagnostics"].append(
            {
                "provider": "duckduckgo",
                "status": "failed",
                "message": "proxy connection refused",
                "proxy_configured": False,
            }
        )
        return []

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", failing_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    _tool_run, web_results, state = await _prepare_web_search_tool_run(
        [{"role": "user", "content": "知识库资料\n\n问题：question"}],
        question="question",
    )

    status = _status_from_web_search_state(web_results, state)

    assert status["status"] == "no_results"
    assert status["errors"] == [
        {
            "source": "duckduckgo",
            "query": "question",
            "message": "proxy connection refused（未配置 HTTP_PROXY）",
        }
    ]


@pytest.mark.asyncio
async def test_only_new_tool_results_are_appended_after_initial_web_context(
    monkeypatch,
):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    async def fake_search_web(query, *, max_results=3):
        if query == "question":
            return [
                {
                    "title": "Initial Web Result",
                    "url": "https://example.com/initial",
                    "snippet": "Initial snippet",
                }
            ]
        return [
            {
                "title": "Extra Web Result",
                "url": "https://example.com/extra",
                "snippet": "Extra snippet",
            }
        ]

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        await kwargs["tool_handlers"]["web_search"]({"query": "extra query"})
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    tool_run, web_results, _state = await _prepare_web_search_tool_run(
        [{"role": "user", "content": "知识库资料\n\n问题：question"}],
        question="question",
    )
    serialized_messages = json.dumps(tool_run.messages, ensure_ascii=False)

    assert len(web_results) == 2
    assert serialized_messages.count("Initial Web Result") == 1
    assert serialized_messages.count("Extra Web Result") == 1


@pytest.mark.asyncio
async def test_tool_web_results_remove_initial_no_results_instruction(monkeypatch):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    captured = {"calls": [], "second_call_messages": []}

    class FakeToolFunction:
        name = "web_search"
        arguments = json.dumps({"query": "tool query"}, ensure_ascii=False)

    class FakeToolCall:
        id = "call_search"
        function = FakeToolFunction()

    class FakeMessage:
        reasoning_content = ""

        def __init__(self, *, content="", tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls

        def model_dump(self, exclude_none=True):
            data = {"role": "assistant", "content": self.content}
            if self.tool_calls is not None:
                data["tool_calls"] = [
                    {
                        "id": "call_search",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ]
            return data

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            if len(captured["calls"]) == 1:
                captured["first_call_messages"] = kwargs["messages"]
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(tool_calls=[FakeToolCall()])},
                            )()
                        ]
                    },
                )()
            captured["second_call_messages"] = kwargs["messages"]
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type("Choice", (), {"message": FakeMessage(content="answer")})()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_search_web(query, *, max_results=3):
        if query == "question":
            return []
        return [
            {
                "title": "Tool Web Result",
                "url": "https://example.com/tool",
                "snippet": "Tool snippet",
            }
        ]

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
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)

    tool_run, web_results, _state = await _prepare_web_search_tool_run(
        [{"role": "user", "content": "知识库资料\n\n问题：question"}],
        question="question",
        provider="tavily",
    )
    serialized_second_call = json.dumps(
        captured["second_call_messages"],
        ensure_ascii=False,
    )
    serialized_final_messages = json.dumps(tool_run.messages, ensure_ascii=False)

    assert len(web_results) == 1
    assert "联网搜索资料" in serialized_second_call
    assert "Tool Web Result" in serialized_second_call
    assert "不要声称已获得外部网页资料" not in serialized_second_call
    assert "联网搜索资料" in serialized_final_messages
    assert "不要声称已获得外部网页资料" not in serialized_final_messages


@pytest.mark.asyncio
async def test_scoped_chat_web_search_does_not_attach_db_fallback_sources(
    client, monkeypatch
):
    await register_user(client, "web-no-db-source@example.com", "Web No Db Source")
    knowledge_base = await create_knowledge_base(client, "Web No Db Source KB")

    class EmptyRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return []

    async def fake_load_db_fallback_documents(*args, **kwargs):
        return [
            type(
                "FakeDocument",
                (),
                {
                    "page_content": "Unrelated database fallback content",
                    "metadata": {
                        "bvid": "BVunrelated",
                        "title": "Unrelated DB Source",
                        "url": "https://www.bilibili.com/video/BVunrelated",
                    },
                },
            )()
        ]

    async def fake_complete_with_web(messages, *, question, enable_web_search):
        assert enable_web_search is True
        assert "Unrelated database fallback content" not in json.dumps(
            messages,
            ensure_ascii=False,
        )
        return (
            "answer from web",
            "",
            [
                {
                    "title": "Relevant Web Source",
                    "url": "https://example.com/relevant",
                    "snippet": "Relevant snippet",
                }
            ],
            {
                "status": "success",
                "message": "已使用联网搜索",
                "result_count": 1,
                "results": [
                    {
                        "title": "Relevant Web Source",
                        "url": "https://example.com/relevant",
                        "snippet": "Relevant snippet",
                    }
                ],
            },
        )

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: EmptyRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._load_db_fallback_documents",
        fake_load_db_fallback_documents,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_knowledge_base_answer",
        fake_complete_with_web,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "查外部资料", "web_search": True},
    )

    assert response.status_code == 200
    sources = response.json()["sources"]
    assert sources == [
        {
            "type": "web",
            "title": "Relevant Web Source",
            "url": "https://example.com/relevant",
        }
    ]


@pytest.mark.asyncio
async def test_scoped_chat_does_not_use_db_fallback_when_vector_search_is_empty(
    client, monkeypatch
):
    await register_user(client, "empty-vector@example.com", "Empty Vector")
    knowledge_base = await create_knowledge_base(client, "Empty Vector KB")
    captured = {"fallback_called": False}

    class EmptyRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return []

    async def fake_load_db_fallback_documents(*args, **kwargs):
        captured["fallback_called"] = True
        return [
            type(
                "FakeDocument",
                (),
                {
                    "page_content": "Unrelated database fallback content",
                    "metadata": {
                        "bvid": "BVunrelated",
                        "title": "Unrelated DB Source",
                        "url": "https://www.bilibili.com/video/BVunrelated",
                    },
                },
            )()
        ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: EmptyRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._load_db_fallback_documents",
        fake_load_db_fallback_documents,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_llm_answer",
        lambda messages: ("不应使用无关兜底资料回答", ""),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "一个与资料无关的问题"},
    )

    assert response.status_code == 200
    assert captured["fallback_called"] is False
    assert response.json()["sources"] == []
    assert "没有找到相关内容" in response.json()["answer"]


@pytest.mark.asyncio
async def test_scoped_chat_adds_initial_web_sources_to_first_answer_context(
    client, monkeypatch
):
    await register_user(
        client, "web-fallback-answer@example.com", "Web Fallback Answer"
    )
    knowledge_base = await create_knowledge_base(client, "Web Fallback Answer KB")
    captured = {"queries": [], "final_messages": []}

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

    class FakeMessage:
        def __init__(self, *, content="", tool_calls=None):
            self.content = content
            self.reasoning_content = ""
            self.tool_calls = tool_calls

        def model_dump(self, exclude_none=True):
            data = {"role": "assistant", "content": self.content}
            if self.tool_calls is not None:
                data["tool_calls"] = [
                    {
                        "id": "call_empty_search",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ]
            return data

    class FakeCompletions:
        def __init__(self):
            self.tool_rounds = 0

        def create(self, **kwargs):
            if "tools" in kwargs:
                self.tool_rounds += 1
                if self.tool_rounds == 1:
                    return type(
                        "Response",
                        (),
                        {
                            "choices": [
                                type(
                                    "Choice",
                                    (),
                                    {
                                        "message": FakeMessage(
                                            tool_calls=[FakeToolCall()]
                                        )
                                    },
                                )()
                            ]
                        },
                    )()
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {
                                    "message": FakeMessage(
                                        content="answer before fallback"
                                    )
                                },
                            )()
                        ]
                    },
                )()
            captured["final_messages"].append(kwargs["messages"])
            assert "Direct Fallback Web" in json.dumps(
                kwargs["messages"], ensure_ascii=False
            )
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="answer with fallback")},
                        )()
                    ]
                },
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

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "original user question", "web_search": True},
    )

    assert response.status_code == 200
    assert captured["queries"] == ["original user question", "model query with no hits"]
    assert captured["final_messages"] == []
    assert response.json()["answer"] == "answer before fallback"
    assert response.json()["web_search"]["status"] == "success"
    assert {
        "type": "web",
        "title": "Direct Fallback Web",
        "url": "https://example.com/direct-fallback",
    } in response.json()["sources"]


@pytest.mark.asyncio
async def test_scoped_chat_can_use_web_search_when_knowledge_base_has_no_hits(
    client, monkeypatch
):
    await register_user(client, "web-only@example.com", "Web Only")
    knowledge_base = await create_knowledge_base(client, "Web Only KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return []

    class FakeToolFunction:
        name = "web_search"
        arguments = json.dumps({"query": "只有外部资料的问题"}, ensure_ascii=False)

    class FakeToolCall:
        id = "call_web_only"
        function = FakeToolFunction()

    class FakeMessage:
        def __init__(self, *, content="", tool_calls=None):
            self.content = content
            self.reasoning_content = ""
            self.tool_calls = tool_calls

        def model_dump(self, exclude_none=True):
            data = {"role": "assistant", "content": self.content}
            if self.tool_calls is not None:
                data["tool_calls"] = [
                    {
                        "id": "call_web_only",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ]
            return data

    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if "tools" in kwargs:
                if self.calls == 1:
                    return type(
                        "Response",
                        (),
                        {
                            "choices": [
                                type(
                                    "Choice",
                                    (),
                                    {
                                        "message": FakeMessage(
                                            tool_calls=[FakeToolCall()]
                                        )
                                    },
                                )()
                            ]
                        },
                    )()
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(content="外部资料答案")},
                            )()
                        ]
                    },
                )()
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="外部资料答案")},
                        )()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_search_web(query, *, max_results=3):
        captured["search_query"] = query
        return [
            {
                "title": "外部来源",
                "url": "https://example.com/web-only",
                "snippet": "外部摘要",
            }
        ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    async def empty_db_fallback(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases._load_db_fallback_documents",
        empty_db_fallback,
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

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "只有外部资料的问题", "web_search": True},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "外部资料答案"
    assert captured["search_query"] == "只有外部资料的问题"
    assert response.json()["sources"] == [
        {
            "type": "web",
            "title": "外部来源",
            "url": "https://example.com/web-only",
        }
    ]
    assert response.json()["web_search"]["status"] == "success"


@pytest.mark.asyncio
async def test_scoped_chat_stream_requires_owned_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice Stream KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.post(
        f"/knowledge-bases/{alice_kb['id']}/chat/stream",
        json={"question": "hello"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_chat_stream_returns_answer_for_owner(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Owner Stream KB")

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Streamed answer chunk.",
                        "metadata": {
                            "bvid": "BV1st411c7mD",
                            "title": "Stream Intro",
                            "url": "https://www.bilibili.com/video/BV1st411c7mD",
                        },
                    },
                )()
            ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "stream please"},
    )

    assert response.status_code == 200
    assert "Streamed answer chunk." in response.text
    assert "[[SOURCES_JSON]]" in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_json_encodes_thinking(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Thinking Stream KB")

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "context",
                        "metadata": {"bvid": "BV1", "title": "Source"},
                    },
                )()
            ]

    def fake_stream_llm_events(messages):
        yield "thinking", "思考"
        yield "answer", "done"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "show thinking"},
    )

    assert response.status_code == 200
    assert '[[THINKING_JSON]]"思考"' in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_uses_configured_thinking(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    accounts_response = await client.get("/api-accounts")
    assert accounts_response.status_code == 200
    account_id = accounts_response.json()[0]["id"]
    update_response = await client.patch(
        f"/api-accounts/{account_id}",
        json={"thinking_config": {"thinking": {"type": "enabled"}}},
    )
    assert update_response.status_code == 200
    knowledge_base = await create_knowledge_base(client, "Native Thinking KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "知识库上下文",
                        "metadata": {
                            "bvid": "BV1thinking",
                            "title": "Thinking Source",
                            "url": "https://www.bilibili.com/video/BV1thinking",
                        },
                    },
                )()
            ]

    def fake_stream_llm_events(messages):
        captured["messages"] = messages
        yield "thinking", "先分析"
        yield "answer", "模型答案"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )
    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "请回答"},
    )

    assert response.status_code == 200
    assert "知识库上下文" in str(captured["messages"])
    assert "原生 reasoning/thinking" in str(captured["messages"])
    assert '[[THINKING_DELTA]]"先分析"' in response.text
    assert "模型答案" in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_emits_empty_sources_trailer(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Empty Stream KB")

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "nothing here"},
    )

    assert response.status_code == 200
    assert "[[SOURCES_JSON]][]" in response.text


@pytest.mark.asyncio
async def test_scoped_chat_unions_folder_and_explicit_video_scope(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Scoped Chat KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Selected folder",
        videos=[("BV1FOLDER", "Folder video")],
    )
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=20,
        title="Explicit video folder",
        videos=[("BV1EXPLICIT", "Explicit video")],
    )
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["bvids"] = bvids
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={
            "question": "scope this",
            "folder_ids": [10],
            "bvids": ["BV1EXPLICIT"],
        },
    )

    assert response.status_code == 200
    assert captured["bvids"] == ["BV1EXPLICIT", "BV1FOLDER"]


@pytest.mark.asyncio
async def test_scoped_search_passes_resolved_video_scope(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Scoped Search KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Selected folder",
        videos=[("BV1SEARCH", "Search video")],
    )
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["bvids"] = bvids
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/search",
        json={"query": "scope this", "folder_ids": [10]},
    )

    assert response.status_code == 200
    assert captured["bvids"] == ["BV1SEARCH"]


@pytest.mark.asyncio
async def test_scoped_chat_stream_uses_same_resolved_scope(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Scoped Stream KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Selected folder",
        videos=[("BV1STREAM", "Stream video")],
    )
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["bvids"] = bvids
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "scope this", "folder_ids": [10]},
    )

    assert response.status_code == 200
    assert captured["bvids"] == ["BV1STREAM"]


@pytest.mark.asyncio
async def test_scoped_chat_rejects_external_bvid(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Alice KB")
    other_knowledge_base = await create_knowledge_base(client, "Other KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=other_knowledge_base,
        media_id=20,
        title="External folder",
        videos=[("BV2EXTERNAL", "External video")],
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: object(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "scope this", "bvids": ["BV2EXTERNAL"]},
    )

    assert response.status_code == 400
    assert "BV2EXTERNAL" in response.json()["detail"]


@pytest.mark.asyncio
async def test_scope_options_only_returns_current_knowledge_base(
    client,
    db_session_factory,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Alice KB")
    other_knowledge_base = await create_knowledge_base(client, "Other KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Current folder",
        videos=[("BV1CURRENT", "Current video")],
    )
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=other_knowledge_base,
        media_id=20,
        title="External folder",
        videos=[("BV2EXTERNAL", "External video")],
    )

    response = await client.get(
        f"/knowledge-bases/{knowledge_base['id']}/scope-options"
    )

    assert response.status_code == 200
    assert response.json() == {
        "folders": [
            {
                "media_id": 10,
                "title": "Current folder",
                "video_count": 1,
                "videos": [
                    {"bvid": "BV1CURRENT", "title": "Current video"},
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_scope_options_requires_login(client):
    response = await client.get("/knowledge-bases/1/scope-options")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scope_options_hides_other_users_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.get(f"/knowledge-bases/{alice_kb['id']}/scope-options")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_build_rejects_unknown_source_binding(client):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Build KB")

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": 999, "folder_ids": [1]},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_build_records_scope_metadata(
    client,
    db_session_factory,
    monkeypatch,
):
    class FakeBilibiliService:
        def __init__(self, **_kwargs):
            pass

        async def close(self):
            pass

    async def fake_run_scoped_build(**_kwargs):
        pass

    monkeypatch.setattr(
        "app.routers.knowledge_bases.BilibiliService",
        FakeBilibiliService,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ASRService",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ContentFetcher",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._run_scoped_build",
        fake_run_scoped_build,
    )

    auth = await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Build Metadata KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": binding.id, "folder_ids": [1, 2]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["workspace_id"] == knowledge_base["workspace_id"]
    assert body["knowledge_base_id"] == knowledge_base["id"]
    assert body["source_binding_id"] == binding.id
    assert body["task_id"]


@pytest.mark.asyncio
async def test_scoped_build_accepts_single_video_selection(
    client,
    db_session_factory,
    monkeypatch,
):
    class FakeBilibiliService:
        def __init__(self, **_kwargs):
            pass

        async def close(self):
            pass

    captured = {}

    async def fake_run_scoped_build(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.routers.knowledge_bases.BilibiliService",
        FakeBilibiliService,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ASRService",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ContentFetcher",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._run_scoped_build",
        fake_run_scoped_build,
    )

    auth = await register_user(client, "video-build@example.com", "Video Build")
    knowledge_base = await create_knowledge_base(client, "Video Build KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={
            "source_binding_id": binding.id,
            "folder_ids": [],
            "video_folder_ids": [10],
            "bvids": ["BV1ONLY"],
        },
    )

    assert response.status_code == 200
    assert captured["folder_ids"] == []
    assert captured["video_folder_ids"] == [10]
    assert captured["include_bvids"] == {"BV1ONLY"}


@pytest.mark.asyncio
async def test_scoped_build_starts_when_vector_service_is_unavailable(
    client,
    db_session_factory,
    monkeypatch,
):
    class FakeBilibiliService:
        def __init__(self, **_kwargs):
            pass

        async def close(self):
            pass

    captured = {}

    async def fake_run_scoped_build(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.routers.knowledge_bases.BilibiliService",
        FakeBilibiliService,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ASRService",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ContentFetcher",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: (_ for _ in ()).throw(RuntimeError("missing embedding key")),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._run_scoped_build",
        fake_run_scoped_build,
    )

    auth = await register_user(client, "no-vector-build@example.com", "No Vector")
    knowledge_base = await create_knowledge_base(client, "No Vector KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": binding.id, "folder_ids": [10]},
    )

    assert response.status_code == 200
    assert captured["rag"].add_video_content(object()) == 0


@pytest.mark.asyncio
async def test_scoped_build_rejects_empty_folder_ids(client, db_session_factory):
    auth = await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Empty Folders KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": binding.id, "folder_ids": []},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "folder_ids cannot be empty"


@pytest.mark.asyncio
async def test_scoped_build_rejects_other_users_source_binding(
    client,
    db_session_factory,
):
    alice_auth = await register_user(client, "alice@example.com", "Alice")
    alice_binding = await create_source_binding(
        db_session_factory,
        user_id=alice_auth["user"]["id"],
        workspace_id=alice_auth["workspace"]["id"],
    )
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    bob_kb = await create_knowledge_base(client, "Bob Build KB")

    response = await client.post(
        f"/knowledge-bases/{bob_kb['id']}/build",
        json={"source_binding_id": alice_binding.id, "folder_ids": [1]},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_build_status_polling_does_not_touch_session_last_seen(
    client,
    db_session_factory,
):
    auth = await register_user(client, "poll-status@example.com", "Poll Status")
    knowledge_base = await create_knowledge_base(client, "Poll Status KB")
    task_id = "poll-status-task"

    async with db_session_factory() as session:
        auth_session = (
            (
                await session.execute(
                    select(SystemSession).where(
                        SystemSession.user_id == auth["user"]["id"]
                    )
                )
            )
            .scalars()
            .first()
        )
        before = auth_session.last_seen_at
        session.add(
            IngestionTask(
                task_id=task_id,
                workspace_id=knowledge_base["workspace_id"],
                knowledge_base_id=knowledge_base["id"],
                source_binding_id=None,
                created_by=auth["user"]["id"],
                status="running",
                progress=42,
                current_step="polling",
            )
        )
        await session.commit()

    response = await client.get(
        f"/knowledge-bases/{knowledge_base['id']}/build/status/{task_id}"
    )

    assert response.status_code == 200
    assert response.json()["progress"] == 42
    async with db_session_factory() as session:
        auth_session = (
            (
                await session.execute(
                    select(SystemSession).where(
                        SystemSession.user_id == auth["user"]["id"]
                    )
                )
            )
            .scalars()
            .first()
        )
        assert auth_session.last_seen_at == before
