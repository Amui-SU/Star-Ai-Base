from app.services.knowledge_base_build_runtime import (
    NoopBuildRAGService,
    resolve_build_rag_service,
)


def test_resolve_build_rag_service_returns_available_service():
    service = object()
    warnings = []

    result = resolve_build_rag_service(
        rag_service_factory=lambda: service,
        warning_logger=warnings.append,
    )

    assert result is service
    assert warnings == []


def test_resolve_build_rag_service_falls_back_when_vector_service_unavailable():
    warnings = []

    def broken_factory():
        raise RuntimeError("missing embedding key")

    result = resolve_build_rag_service(
        rag_service_factory=broken_factory,
        warning_logger=warnings.append,
    )

    assert isinstance(result, NoopBuildRAGService)
    assert result.add_video_content(object()) == 0
    assert result.delete_video("BV1") is None
    assert result.delete_video_in_knowledge_base("BV1", knowledge_base_id=2) is None
    assert "missing embedding key" in warnings[0]
