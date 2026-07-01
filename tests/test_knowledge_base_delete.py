import pytest
from fastapi import HTTPException

from app.models import KnowledgeBase, Workspace
from app.services.knowledge_base_delete import delete_knowledge_base


@pytest.mark.asyncio
async def test_delete_knowledge_base_uses_workspace_scoped_vector_cleanup(
    db_session_factory,
):
    async with db_session_factory() as session:
        workspace = Workspace(name="Delete workspace", owner_user_id=1)
        session.add(workspace)
        await session.flush()
        knowledge_base = KnowledgeBase(
            name="Delete KB",
            workspace_id=workspace.id,
            created_by=1,
        )
        session.add(knowledge_base)
        await session.commit()
        await session.refresh(knowledge_base)

        calls = []

        class ScopedRag:
            def delete_by_knowledge_base(self, knowledge_base_id, workspace_id=None):
                calls.append(
                    {
                        "knowledge_base_id": knowledge_base_id,
                        "workspace_id": workspace_id,
                    }
                )
                return 7

        result = await delete_knowledge_base(
            session,
            knowledge_base=knowledge_base,
            workspace=workspace,
            rag_service_factory=lambda: ScopedRag(),
        )

        assert result == {"ok": True, "deleted_vectors": 7}
        assert calls == [
            {
                "knowledge_base_id": knowledge_base.id,
                "workspace_id": workspace.id,
            }
        ]
        assert await session.get(KnowledgeBase, knowledge_base.id) is None


@pytest.mark.asyncio
async def test_delete_knowledge_base_keeps_record_when_vector_cleanup_fails(
    db_session_factory,
):
    async with db_session_factory() as session:
        workspace = Workspace(name="Failed delete workspace", owner_user_id=1)
        session.add(workspace)
        await session.flush()
        knowledge_base = KnowledgeBase(
            name="Failed Delete KB",
            workspace_id=workspace.id,
            created_by=1,
        )
        session.add(knowledge_base)
        await session.commit()
        await session.refresh(knowledge_base)

        class BrokenRag:
            def delete_by_knowledge_base(self, knowledge_base_id, workspace_id=None):
                raise RuntimeError("vector store locked")

        with pytest.raises(HTTPException) as exc_info:
            await delete_knowledge_base(
                session,
                knowledge_base=knowledge_base,
                workspace=workspace,
                rag_service_factory=lambda: BrokenRag(),
            )

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["code"] == "vector_cleanup_failed"
        assert "vector store locked" in exc_info.value.detail["message"]
        assert await session.get(KnowledgeBase, knowledge_base.id) is not None
