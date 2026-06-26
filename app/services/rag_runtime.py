"""Runtime access to the process-local RAG service."""

from typing import Optional

from app.services.rag import RAGService

_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Return the lazily initialized RAG service singleton."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


def reset_rag_service() -> None:
    """Drop the cached RAG service so provider/config changes take effect."""
    global _rag_service
    _rag_service = None
