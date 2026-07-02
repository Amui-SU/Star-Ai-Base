"""RAG vector indexing helpers."""

from collections.abc import Callable, Sequence
from typing import Any

from loguru import logger

from app.schemas.content import VideoContent
from app.services.rag_documents import build_video_content_text, build_video_documents


def index_video_content(
    video: VideoContent,
    *,
    vectorstore: Any,
    text_splitter: Any,
    workspace_id: int | None = None,
    knowledge_base_id: int | None = None,
    source_binding_id: int | None = None,
    batch_size: int = 10,
    warning_logger: Callable[[str], None] = logger.warning,
    info_logger: Callable[[str], None] = logger.info,
    error_logger: Callable[[str], None] = logger.error,
) -> int:
    """Build vector documents for one video and write them in small batches."""
    full_content = build_video_content_text(video)
    if not full_content or len(full_content.strip()) < 10:
        warning_logger(f"[{video.bvid}] 内容太少，跳过")
        return 0

    if workspace_id is None or knowledge_base_id is None:
        warning_logger(f"[{video.bvid}] 缺少多用户范围元数据，按旧模式写入")

    documents = build_video_documents(
        video,
        text_splitter=text_splitter,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=source_binding_id,
    )
    if not documents:
        warning_logger(f"[{video.bvid}] 没有有效的文档块")
        return 0

    try:
        for idx in range(0, len(documents), batch_size):
            vectorstore.add_documents(documents[idx : idx + batch_size])
        info_logger(f"[{video.bvid}] 添加了 {len(documents)} 个文档块")
    except Exception as exc:
        error_logger(f"[{video.bvid}] 添加到向量库失败: {exc}")
        raise

    return len(documents)


def index_videos_batch(
    videos: Sequence[VideoContent],
    *,
    add_video_content: Callable[[VideoContent], int],
    progress_callback: Callable[[int, int, str], None] | None = None,
    error_logger: Callable[[str], None] = logger.error,
) -> dict:
    """Index videos one by one while preserving legacy batch counters."""
    success = 0
    failed = 0
    total_chunks = 0

    for index, video in enumerate(videos):
        try:
            chunks = add_video_content(video)
            total_chunks += chunks
            success += 1

            if progress_callback:
                progress_callback(index + 1, len(videos), video.title)
        except Exception as exc:
            error_logger(f"添加视频失败 [{video.bvid}]: {exc}")
            failed += 1

    return {"success": success, "failed": failed, "chunks": total_chunks}
