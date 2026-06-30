from app import models
from app.schemas.api_accounts import ApiAccountCreateRequest, ApiAccountResponse
from app.schemas.auth import SystemLoginRequest, SystemUserResponse
from app.schemas.content import ContentSource, FavoriteFolderInfo, VideoContent
from app.schemas.knowledge_base import (
    KnowledgeBaseBuildRequest,
    KnowledgeBaseChatRequest,
    KnowledgeBaseCreateRequest,
)
from app.schemas.source_bindings import LoginStatusResponse, SourceBindingResponse


def test_auth_schemas_are_reexported_from_legacy_models_module():
    assert models.SystemLoginRequest is SystemLoginRequest
    assert models.SystemUserResponse is SystemUserResponse

    login = models.SystemLoginRequest(email="user@example.com", password="secret")
    user = models.SystemUserResponse(
        id=1,
        email="user@example.com",
        display_name="User",
    )

    assert login.email == "user@example.com"
    assert user.is_admin is False


def test_api_account_schemas_are_reexported_from_legacy_models_module():
    assert models.ApiAccountCreateRequest is ApiAccountCreateRequest
    assert models.ApiAccountResponse is ApiAccountResponse

    request = models.ApiAccountCreateRequest(provider="deepseek", api_key="sk-test")
    response = models.ApiAccountResponse(
        id=1,
        provider="deepseek",
        provider_label="DeepSeek",
        display_name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        enabled=True,
        is_default=False,
    )

    assert request.is_default is False
    assert response.configured is True


def test_knowledge_base_schemas_are_reexported_from_legacy_models_module():
    assert models.KnowledgeBaseCreateRequest is KnowledgeBaseCreateRequest
    assert models.KnowledgeBaseBuildRequest is KnowledgeBaseBuildRequest
    assert models.KnowledgeBaseChatRequest is KnowledgeBaseChatRequest

    build_request = models.KnowledgeBaseBuildRequest(
        source_binding_id=3,
        folder_ids=[10],
        video_folder_ids=[10],
        bvids=["BV1xx411c7mD"],
    )
    chat_request = models.KnowledgeBaseChatRequest(
        question="hello",
        web_search=True,
        web_search_provider="TAVILY",
    )

    assert build_request.exclude_bvids is None
    assert chat_request.web_search_provider == "tavily"


def test_content_schemas_are_reexported_from_legacy_models_module():
    assert models.ContentSource is ContentSource
    assert models.VideoContent is VideoContent
    assert models.FavoriteFolderInfo is FavoriteFolderInfo

    content = models.VideoContent(
        bvid="BV1xx411c7mD",
        title="Title",
        content="Body",
        source=models.ContentSource.ASR,
    )
    folder = models.FavoriteFolderInfo(
        media_id=10,
        title="Folder",
        media_count=3,
    )

    assert content.source == ContentSource.ASR
    assert folder.is_selected is True


def test_source_binding_schemas_are_reexported_from_legacy_models_module():
    assert models.SourceBindingResponse is SourceBindingResponse
    assert models.LoginStatusResponse is LoginStatusResponse

    binding = models.SourceBindingResponse(
        id=1,
        source_type="bilibili",
        external_account_id="42",
        status="active",
    )
    status = models.LoginStatusResponse(status="waiting", message="scan")

    assert binding.external_account_name is None
    assert status.session_id is None
