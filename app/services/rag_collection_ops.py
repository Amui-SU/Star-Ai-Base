"""Low-level collection operations for RAG vector storage."""

from loguru import logger

from app.services.rag_filters import (
    knowledge_base_filter,
    video_in_knowledge_base_filter,
)


def collection_stats(collection, *, collection_name: str) -> dict:
    try:
        count = collection.count()
        result = collection.get(include=["metadatas"])
        bvids = set()
        for meta in result.get("metadatas", []):
            if meta and "bvid" in meta:
                bvids.add(meta["bvid"])

        return {
            "total_chunks": count,
            "total_videos": len(bvids),
            "collection_name": collection_name,
        }
    except Exception as exc:
        logger.error(f"获取统计信息失败: {exc}")
        return {
            "total_chunks": 0,
            "total_videos": 0,
            "collection_name": collection_name,
        }


def clear_collection(collection) -> None:
    collection.delete(where={})


def delete_video_vectors(collection, *, bvid: str) -> None:
    collection.delete(where={"bvid": bvid})


def delete_video_vectors_in_knowledge_base(
    collection,
    *,
    workspace_id: int,
    knowledge_base_id: int,
    bvid: str,
) -> None:
    collection.delete(
        where=video_in_knowledge_base_filter(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            bvid=bvid,
        )
    )


def has_video_vectors_in_knowledge_base(
    collection,
    *,
    workspace_id: int,
    knowledge_base_id: int,
    bvid: str,
) -> bool:
    where = video_in_knowledge_base_filter(
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        bvid=bvid,
    )
    result = collection.get(where=where, limit=1)
    return bool(result.get("ids"))


def delete_knowledge_base_vectors(
    collection,
    *,
    knowledge_base_id: int,
    workspace_id: int | None = None,
) -> int:
    if workspace_id is None:
        where = {"knowledge_base_id": knowledge_base_id}
    else:
        where = knowledge_base_filter(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
        )
    before = collection.count()
    collection.delete(where=where)
    after = collection.count()
    return before - after
