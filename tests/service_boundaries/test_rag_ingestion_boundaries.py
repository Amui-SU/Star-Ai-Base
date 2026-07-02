from tests.service_boundaries.helpers import get_project_root


def test_folder_ingestion_delegates_records_and_content_helpers_to_services():
    project_root = get_project_root()
    ingestion_path = project_root / "app/services/folder_ingestion.py"
    records_path = project_root / "app/services/folder_ingestion_records.py"
    content_path = project_root / "app/services/folder_ingestion_content.py"
    vector_runtime_path = (
        project_root / "app/services/folder_ingestion_vector_runtime.py"
    )

    ingestion_source = ingestion_path.read_text(encoding="utf-8")

    assert records_path.exists()
    records_source = records_path.read_text(encoding="utf-8")
    for name in {
        "has_cache_scope",
        "get_or_create_folder",
        "get_existing_folder_for_scope",
        "get_video_cache_for_scope",
        "delete_video_vectors_for_scope",
        "upsert_video_cache",
    }:
        assert f"def {name}" in records_source or f"async def {name}" in records_source

    assert content_path.exists()
    content_source = content_path.read_text(encoding="utf-8")
    for name in {
        "extract_video_info",
        "is_better_source",
        "should_refresh_cache",
        "is_asr_cache_usable",
        "video_content_from_cache",
    }:
        assert f"def {name}" in content_source

    assert "from app.services.folder_ingestion_records import" in ingestion_source
    assert "from app.services.folder_ingestion_content import" in ingestion_source
    assert vector_runtime_path.exists()
    vector_runtime_source = vector_runtime_path.read_text(encoding="utf-8")
    for name in {
        "has_scoped_vectors",
        "process_vector_target",
    }:
        assert (
            f"def {name}" in vector_runtime_source
            or f"async def {name}" in vector_runtime_source
        )
    assert (
        "from app.services.folder_ingestion_vector_runtime import" in ingestion_source
    )
    assert "select(VideoCache)" not in ingestion_source
    assert "VideoCache(" not in ingestion_source
    assert "source_priority =" not in ingestion_source
    assert "def _is_better_source" not in ingestion_source
    assert "def _should_refresh_cache" not in ingestion_source
    assert "def _video_content_from_cache" not in ingestion_source
    assert "def _has_scoped_vectors" not in ingestion_source
    assert (
        'getattr(rag, "has_video_vectors_in_knowledge_base", None)'
        not in ingestion_source
    )
    assert "content_fetcher.fetch_content(" not in ingestion_source
    assert 'old_content = (cache.content or "").strip()' not in ingestion_source


def test_rag_service_delegates_document_and_filter_helpers_to_services():
    project_root = get_project_root()
    documents_path = project_root / "app/services/rag_documents.py"
    filters_path = project_root / "app/services/rag_filters.py"
    collection_ops_path = project_root / "app/services/rag_collection_ops.py"
    runtime_path = project_root / "app/services/rag_runtime_components.py"
    qa_path = project_root / "app/services/rag_qa.py"
    rag_source = (project_root / "app/services/rag.py").read_text(encoding="utf-8")

    assert documents_path.exists()
    documents_source = documents_path.read_text(encoding="utf-8")
    for name in {
        "build_video_content_text",
        "build_video_documents",
    }:
        assert f"def {name}" in documents_source

    assert filters_path.exists()
    filters_source = filters_path.read_text(encoding="utf-8")
    for name in {
        "knowledge_base_filter",
        "video_in_knowledge_base_filter",
    }:
        assert f"def {name}" in filters_source

    assert "from app.services.rag_documents import" in rag_source
    assert "from app.services.rag_filters import" in rag_source
    assert runtime_path.exists()
    runtime_source = runtime_path.read_text(encoding="utf-8")
    for name in {
        "build_embeddings",
        "build_vectorstore",
        "build_llm",
        "build_text_splitter",
        "build_qa_prompt",
        "build_fallback_prompt",
        "build_summary_prompt",
    }:
        assert f"def {name}" in runtime_source
    assert "from app.services.rag_runtime_components import" in rag_source
    assert collection_ops_path.exists()
    collection_ops_source = collection_ops_path.read_text(encoding="utf-8")
    for name in {
        "collection_stats",
        "clear_collection",
        "delete_video_vectors",
        "delete_video_vectors_in_knowledge_base",
        "has_video_vectors_in_knowledge_base",
        "delete_knowledge_base_vectors",
    }:
        assert f"def {name}" in collection_ops_source
    assert "from app.services.rag_collection_ops import" in rag_source
    assert qa_path.exists()
    qa_source = qa_path.read_text(encoding="utf-8")
    for name in {
        "answer_rag_question",
        "build_rag_answer_context_and_sources",
        "complete_rag_answer",
        "fallback_rag_answer",
    }:
        assert f"def {name}" in qa_source or f"async def {name}" in qa_source
    assert "from app.services.rag_qa import" in rag_source
    assert "from langchain_openai import OpenAIEmbeddings, ChatOpenAI" not in rag_source
    assert "from langchain_chroma import Chroma" not in rag_source
    assert "RecursiveCharacterTextSplitter" not in rag_source
    assert "ChatPromptTemplate.from_messages" not in rag_source
    assert "Document(" not in rag_source
    assert "context_parts = []" not in rag_source
    assert "seen_bvids = set()" not in rag_source
    assert '"知识库目前还没有内容"' not in rag_source
    assert "AI 回答时发生错误" not in rag_source
    assert "self.vectorstore._collection.delete(" not in rag_source
    assert "self.vectorstore._collection.get(" not in rag_source
    assert "self.vectorstore._collection.count(" not in rag_source
    assert 'filters = [\n            {"workspace_id": workspace_id}' not in rag_source
    assert '{"bvid": {"$in": normalized_bvids}}' not in rag_source


def test_favorite_router_uses_shared_default_folder_detection():
    project_root = get_project_root()
    router_source = (project_root / "app/routers/favorites.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (
        project_root / "app/services/favorites_route_runtime.py"
    ).read_text(encoding="utf-8")

    assert "def _is_default_folder" not in router_source
    assert "def _is_default_folder" not in runtime_source
    assert "is_legacy_default_favorite_folder" in (router_source + runtime_source)
