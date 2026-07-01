"""Runtime helpers for knowledge-base build jobs."""

from collections.abc import Callable
from typing import Any


class NoopBuildRAGService:
    def delete_video(self, *_args, **_kwargs):
        return None

    def delete_video_in_knowledge_base(self, *_args, **_kwargs):
        return None

    def add_video_content(self, *_args, **_kwargs):
        return 0


def resolve_build_rag_service(
    *,
    rag_service_factory: Callable[[], Any],
    warning_logger: Callable[[str], None],
):
    try:
        return rag_service_factory()
    except Exception as exc:
        warning_logger(
            f"知识库向量服务不可用，入库将仅写入数据库内容并跳过向量化: {exc}"
        )
        return NoopBuildRAGService()
