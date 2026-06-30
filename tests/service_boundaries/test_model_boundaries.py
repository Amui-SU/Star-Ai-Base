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
