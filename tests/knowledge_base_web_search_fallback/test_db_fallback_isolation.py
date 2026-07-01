import json

import pytest

from tests.knowledge_base_web_search_fallback.helpers import (
    create_knowledge_base,
    fake_document,
    register_user,
)


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
            fake_document(
                "Unrelated database fallback content",
                {
                    "bvid": "BVunrelated",
                    "title": "Unrelated DB Source",
                    "url": "https://www.bilibili.com/video/BVunrelated",
                },
            )
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
            fake_document(
                "Unrelated database fallback content",
                {
                    "bvid": "BVunrelated",
                    "title": "Unrelated DB Source",
                    "url": "https://www.bilibili.com/video/BVunrelated",
                },
            )
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
