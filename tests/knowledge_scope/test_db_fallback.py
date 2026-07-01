import pytest

from app.models import FavoriteFolder, FavoriteVideo, VideoCache
from tests.knowledge_scope.helpers import create_knowledge_base, register_user


@pytest.mark.asyncio
async def test_chat_falls_back_to_database_content_when_vector_retrieval_fails(
    client, db_session_factory, monkeypatch
):
    await register_user(client, "rag-error@example.com", display_name="RAG Error User")
    account_response = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "api_key": "sk-test-user",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "is_default": True,
        },
    )
    assert account_response.status_code == 200

    knowledge_base = await create_knowledge_base(client, "RAG Error KB")

    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id="rag-error-session",
            workspace_id=knowledge_base["workspace_id"],
            knowledge_base_id=knowledge_base["id"],
            media_id=101,
            title="AI 学习",
            media_count=1,
        )
        session.add(folder)
        await session.flush()
        session.add(
            FavoriteVideo(
                folder_id=folder.id,
                bvid="BV1fallback",
                workspace_id=knowledge_base["workspace_id"],
                knowledge_base_id=knowledge_base["id"],
            )
        )
        session.add(
            VideoCache(
                bvid="BV1fallback",
                title="DeepSeek 入门",
                content="DeepSeek 可以用于知识库问答。",
                is_processed=True,
                workspace_id=knowledge_base["workspace_id"],
                knowledge_base_id=knowledge_base["id"],
            )
        )
        await session.commit()

    def broken_rag():
        raise RuntimeError("missing embedding key")

    monkeypatch.setattr("app.routers.knowledge_bases.get_rag_service", broken_rag)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_llm_answer",
        lambda messages: ("已根据资料回答：DeepSeek 可以用于知识库问答。", ""),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "hello"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "DeepSeek" in body["answer"]
    assert body["sources"][0]["bvid"] == "BV1fallback"
