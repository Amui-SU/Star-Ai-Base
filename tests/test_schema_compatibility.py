from app import models
from app.schemas.api_accounts import ApiAccountCreateRequest, ApiAccountResponse
from app.schemas.auth import SystemLoginRequest, SystemUserResponse
from app.schemas.knowledge_base import (
    KnowledgeBaseBuildRequest,
    KnowledgeBaseChatRequest,
    KnowledgeBaseCreateRequest,
)


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
