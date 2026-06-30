"""Chroma filter helpers for scoped RAG vector operations."""


def knowledge_base_filter(
    *,
    workspace_id: int,
    knowledge_base_id: int,
    bvids: list[str] | None = None,
) -> dict:
    filters = [
        {"workspace_id": workspace_id},
        {"knowledge_base_id": knowledge_base_id},
    ]
    normalized_bvids = sorted(set(bvids or []))
    if normalized_bvids:
        filters.append({"bvid": {"$in": normalized_bvids}})
    return {"$and": filters}


def video_in_knowledge_base_filter(
    *,
    workspace_id: int,
    knowledge_base_id: int,
    bvid: str,
) -> dict:
    return {
        "$and": [
            {"workspace_id": workspace_id},
            {"knowledge_base_id": knowledge_base_id},
            {"bvid": bvid},
        ]
    }
