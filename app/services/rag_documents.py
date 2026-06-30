"""Document construction helpers for RAG vector storage."""

from collections.abc import Sequence
from typing import Any

from langchain.schema import Document

from app.models import VideoContent


def build_video_content_text(video: VideoContent) -> str:
    content_parts: list[str] = []

    if video.content and video.content.strip():
        content_parts.append(video.content.strip())

    if video.outline:
        outline_text = "\n## 内容提纲\n"
        for item in video.outline:
            item_title = item.get("title", "") or ""
            outline_text += f"\n### {item_title}\n"
            for point in item.get("points", []):
                point_content = point.get("content", "") or ""
                if point_content:
                    outline_text += f"- {point_content}\n"
        if outline_text.strip() != "## 内容提纲":
            content_parts.append(outline_text)

    return "\n\n".join(content_parts).strip()


def build_video_documents(
    video: VideoContent,
    *,
    text_splitter: Any,
    workspace_id: int | None = None,
    knowledge_base_id: int | None = None,
    source_binding_id: int | None = None,
) -> list[Document]:
    full_content = build_video_content_text(video)
    chunks: Sequence[str] = text_splitter.split_text(full_content)
    valid_chunks = [chunk for chunk in chunks if chunk and chunk.strip()]
    title = video.title or "未知标题"

    documents = []
    for index, chunk in enumerate(valid_chunks):
        metadata = {
            "workspace_id": workspace_id,
            "knowledge_base_id": knowledge_base_id,
            "source_binding_id": source_binding_id,
            "bvid": video.bvid,
            "title": title,
            "source": video.source.value,
            "chunk_index": index,
            "url": f"https://www.bilibili.com/video/{video.bvid}",
        }
        documents.append(
            Document(
                page_content=chunk.strip(),
                metadata={
                    key: value for key, value in metadata.items() if value is not None
                },
            )
        )

    return documents
