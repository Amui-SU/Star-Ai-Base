from app import models
from app.schemas.api_accounts import ApiAccountCreateRequest, ApiAccountResponse
from app.schemas.auth import SystemLoginRequest, SystemUserResponse


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
