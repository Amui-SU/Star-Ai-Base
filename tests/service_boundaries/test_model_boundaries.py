from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import get_project_root


def test_models_delegates_auth_and_api_account_schemas_to_schema_modules():
    project_root = get_project_root()
    models_source = (project_root / "app/models.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(models_source)

    auth_schema_path = project_root / "app/schemas/auth.py"
    api_accounts_schema_path = project_root / "app/schemas/api_accounts.py"

    auth_schema_names = {
        "SystemRegisterRequest",
        "SystemLoginRequest",
        "SystemDisplayNameUpdateRequest",
        "SystemUserResponse",
        "AdminUserResponse",
        "AdminUserListResponse",
        "AdminUserStatusUpdateRequest",
        "AdminPasswordResetResponse",
        "WorkspaceResponse",
        "SystemAuthResponse",
    }
    api_account_schema_names = {
        "ApiAccountCreateRequest",
        "ApiAccountUpdateRequest",
        "ApiAccountResponse",
    }

    assert auth_schema_path.exists()
    auth_schema_source = auth_schema_path.read_text(encoding="utf-8")
    for name in auth_schema_names:
        assert f"class {name}" in auth_schema_source

    assert api_accounts_schema_path.exists()
    api_accounts_schema_source = api_accounts_schema_path.read_text(encoding="utf-8")
    for name in api_account_schema_names:
        assert f"class {name}" in api_accounts_schema_source

    assert "from app.schemas.auth import" in models_source
    assert "from app.schemas.api_accounts import" in models_source
    assert declared_names.isdisjoint(auth_schema_names | api_account_schema_names)


def test_models_delegates_knowledge_base_schemas_to_schema_module():
    project_root = get_project_root()
    models_source = (project_root / "app/models.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(models_source)

    knowledge_schema_path = project_root / "app/schemas/knowledge_base.py"
    knowledge_schema_names = {
        "KnowledgeBaseCreateRequest",
        "KnowledgeBaseResponse",
        "KnowledgeBaseSearchRequest",
        "KnowledgeBaseSearchResult",
        "KnowledgeBaseSearchResponse",
        "KnowledgeBaseChatRequest",
        "KnowledgeScopeVideo",
        "KnowledgeScopeFolder",
        "KnowledgeScopeOptionsResponse",
        "KnowledgeBaseBuildRequest",
        "KnowledgeBaseBuildResponse",
    }

    assert knowledge_schema_path.exists()
    knowledge_schema_source = knowledge_schema_path.read_text(encoding="utf-8")
    for name in knowledge_schema_names:
        assert f"class {name}" in knowledge_schema_source

    assert "from app.schemas.knowledge_base import" in models_source
    assert declared_names.isdisjoint(knowledge_schema_names)


def test_models_delegates_source_and_content_schemas_to_schema_modules():
    project_root = get_project_root()
    models_source = (project_root / "app/models.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(models_source)

    content_schema_path = project_root / "app/schemas/content.py"
    source_binding_schema_path = project_root / "app/schemas/source_bindings.py"

    content_schema_names = {
        "ContentSource",
        "VideoInfo",
        "VideoContent",
        "FavoriteFolderInfo",
    }
    source_binding_schema_names = {
        "SourceBindingResponse",
        "QRCodeResponse",
        "LoginStatusResponse",
    }

    assert content_schema_path.exists()
    content_schema_source = content_schema_path.read_text(encoding="utf-8")
    for name in content_schema_names:
        assert f"class {name}" in content_schema_source

    assert source_binding_schema_path.exists()
    source_binding_schema_source = source_binding_schema_path.read_text(
        encoding="utf-8"
    )
    for name in source_binding_schema_names:
        assert f"class {name}" in source_binding_schema_source

    assert "from app.schemas.content import" in models_source
    assert "from app.schemas.source_bindings import" in models_source
    assert declared_names.isdisjoint(content_schema_names | source_binding_schema_names)


def test_models_delegates_chat_schemas_to_schema_module():
    project_root = get_project_root()
    models_source = (project_root / "app/models.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(models_source)

    chat_schema_path = project_root / "app/schemas/chat.py"
    chat_schema_names = {
        "ChatRequest",
        "ChatResponse",
        "ChatHistoryMessageRequest",
        "ChatConversationSaveRequest",
        "ChatHistoryMessageResponse",
        "ChatConversationSummaryResponse",
        "ChatConversationResponse",
        "ChatConversationListResponse",
    }

    assert chat_schema_path.exists()
    chat_schema_source = chat_schema_path.read_text(encoding="utf-8")
    for name in chat_schema_names:
        assert f"class {name}" in chat_schema_source

    assert "from app.schemas.chat import" in models_source
    assert declared_names.isdisjoint(chat_schema_names)


def test_models_delegates_content_ingestion_orm_models_to_focused_module():
    project_root = get_project_root()
    models_source = (project_root / "app/models.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(models_source)

    base_model_path = project_root / "app/models_base.py"
    content_model_path = project_root / "app/models_content.py"
    content_model_names = {
        "VideoCache",
        "FavoriteFolder",
        "FavoriteVideo",
        "VideoTitleOverride",
        "IngestionTask",
    }

    assert base_model_path.exists()
    base_model_source = base_model_path.read_text(encoding="utf-8")
    assert "Base = declarative_base()" in base_model_source
    assert "def _utc_now" in base_model_source

    assert content_model_path.exists()
    content_model_source = content_model_path.read_text(encoding="utf-8")
    assert "from app.models_base import Base" in content_model_source
    assert "from app.models_base import _utc_now" in content_model_source
    for name in content_model_names:
        assert f"class {name}(Base)" in content_model_source

    assert "from app.models_base import" in models_source
    assert "from app.models_content import" in models_source
    assert declared_names.isdisjoint(content_model_names)


def test_models_delegates_video_note_orm_models_to_focused_module():
    project_root = get_project_root()
    models_source = (project_root / "app/models.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(models_source)

    note_model_path = project_root / "app/models_notes.py"
    note_model_names = {"VideoNote"}

    assert note_model_path.exists()
    note_model_source = note_model_path.read_text(encoding="utf-8")
    assert "from app.models_base import Base" in note_model_source
    assert "from app.models_base import _utc_now" in note_model_source
    assert "class VideoNote(Base)" in note_model_source
    assert '__tablename__ = "video_notes"' in note_model_source

    assert "from app.models_notes import" in models_source
    assert declared_names.isdisjoint(note_model_names)
