import pytest
from sqlalchemy import select

from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    VideoCache,
    VideoTitleOverride,
)
from tests.knowledge_scope.helpers import create_knowledge_base, register_user


@pytest.mark.asyncio
async def test_delete_knowledge_base_keeps_record_when_vector_cleanup_fails(
    client, monkeypatch
):
    await register_user(client, "delete@example.com", display_name="Delete User")
    knowledge_base = await create_knowledge_base(client, "Delete Target")

    class BrokenRag:
        def delete_by_knowledge_base(self, knowledge_base_id: int):
            raise RuntimeError("missing api key")

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service", lambda: BrokenRag()
    )

    delete_response = await client.delete(f"/knowledge-bases/{knowledge_base['id']}")
    assert delete_response.status_code == 503
    payload = delete_response.json()
    assert payload["detail"]["code"] == "vector_cleanup_failed"
    assert "missing api key" in payload["detail"]["message"]

    list_response = await client.get("/knowledge-bases")
    assert list_response.status_code == 200
    assert any(item["id"] == knowledge_base["id"] for item in list_response.json())


@pytest.mark.asyncio
async def test_delete_knowledge_base_does_not_retry_without_workspace_on_runtime_type_error(
    client, monkeypatch
):
    await register_user(
        client,
        "delete-type-error@example.com",
        display_name="Delete Type Error User",
    )
    knowledge_base = await create_knowledge_base(client, "Delete Type Error Target")
    calls = []

    class BrokenScopedRag:
        def delete_by_knowledge_base(self, knowledge_base_id: int, workspace_id=None):
            calls.append(
                {
                    "knowledge_base_id": knowledge_base_id,
                    "workspace_id": workspace_id,
                }
            )
            if workspace_id is not None:
                raise TypeError("internal vector store type mismatch")
            return 999

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service", lambda: BrokenScopedRag()
    )

    delete_response = await client.delete(f"/knowledge-bases/{knowledge_base['id']}")

    assert delete_response.status_code == 503
    payload = delete_response.json()
    assert payload["detail"]["code"] == "vector_cleanup_failed"
    assert "internal vector store type mismatch" in payload["detail"]["message"]
    assert calls == [
        {
            "knowledge_base_id": knowledge_base["id"],
            "workspace_id": knowledge_base["workspace_id"],
        }
    ]
    list_response = await client.get("/knowledge-bases")
    assert list_response.status_code == 200
    assert any(item["id"] == knowledge_base["id"] for item in list_response.json())


@pytest.mark.asyncio
async def test_delete_knowledge_base_removes_scoped_records_on_success(
    client, db_session_factory, monkeypatch
):
    auth = await register_user(
        client,
        "delete-success@example.com",
        display_name="Delete Success User",
    )
    knowledge_base = await create_knowledge_base(client, "Delete Success Target")

    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id=f"delete-success-{knowledge_base['id']}",
            workspace_id=knowledge_base["workspace_id"],
            knowledge_base_id=knowledge_base["id"],
            media_id=8801,
            title="Delete folder",
        )
        session.add(folder)
        await session.flush()
        video = FavoriteVideo(
            folder_id=folder.id,
            bvid="BVDELETE1",
            workspace_id=knowledge_base["workspace_id"],
            knowledge_base_id=knowledge_base["id"],
        )
        session.add(video)
        video_cache = VideoCache(
            bvid="BVDELETE1",
            title="Delete cache",
            is_processed=True,
            workspace_id=knowledge_base["workspace_id"],
            knowledge_base_id=knowledge_base["id"],
        )
        session.add(video_cache)
        session.add(
            IngestionTask(
                task_id="delete-success-task",
                workspace_id=knowledge_base["workspace_id"],
                knowledge_base_id=knowledge_base["id"],
                source_binding_id=1,
                created_by=auth["user"]["id"],
                status="completed",
            )
        )
        session.add(
            VideoTitleOverride(
                workspace_id=knowledge_base["workspace_id"],
                knowledge_base_id=knowledge_base["id"],
                source_binding_id=None,
                bvid="BVDELETE1",
                custom_title="Custom delete title",
                created_by=auth["user"]["id"],
            )
        )
        await session.commit()

    class CleanRag:
        def delete_by_knowledge_base(self, knowledge_base_id: int, workspace_id=None):
            assert knowledge_base_id == knowledge_base["id"]
            assert workspace_id == knowledge_base["workspace_id"]
            return 3

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service", lambda: CleanRag()
    )

    delete_response = await client.delete(f"/knowledge-bases/{knowledge_base['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_vectors"] == 3

    async with db_session_factory() as session:
        assert await session.get(FavoriteFolder, folder.id) is None
        assert await session.get(FavoriteVideo, video.id) is None
        assert await session.get(VideoCache, video_cache.id) is None
        video_cache_rows = (
            (
                await session.execute(
                    select(VideoCache).where(
                        VideoCache.knowledge_base_id == knowledge_base["id"]
                    )
                )
            )
            .scalars()
            .all()
        )
        assert video_cache_rows == []
        task_rows = (
            (
                await session.execute(
                    select(IngestionTask).where(
                        IngestionTask.knowledge_base_id == knowledge_base["id"]
                    )
                )
            )
            .scalars()
            .all()
        )
        assert task_rows == []
        title_rows = (
            (
                await session.execute(
                    select(VideoTitleOverride).where(
                        VideoTitleOverride.knowledge_base_id == knowledge_base["id"]
                    )
                )
            )
            .scalars()
            .all()
        )
        assert title_rows == []
