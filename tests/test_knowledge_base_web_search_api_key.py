import pytest

from app.services.knowledge_base_web_search_api_key import resolve_web_search_api_key


class FakeCredential:
    def __init__(self, api_key: str):
        self.api_key = api_key


@pytest.mark.asyncio
async def test_web_search_api_key_is_empty_when_search_disabled():
    async def fail_if_called(db, user, provider):
        raise AssertionError("disabled web search should not resolve credentials")

    result = await resolve_web_search_api_key(
        "db",
        "user",
        enabled=False,
        provider="tavily",
        resolve_optional_user_api_credentials=fail_if_called,
    )

    assert result is None


@pytest.mark.asyncio
async def test_web_search_api_key_is_empty_for_html_provider():
    async def fail_if_called(db, user, provider):
        raise AssertionError("html provider should not resolve credentials")

    result = await resolve_web_search_api_key(
        "db",
        "user",
        enabled=True,
        provider="html",
        resolve_optional_user_api_credentials=fail_if_called,
    )

    assert result is None


@pytest.mark.asyncio
async def test_web_search_api_key_uses_tavily_user_credentials():
    calls = []

    async def resolve_credentials(db, user, provider):
        calls.append((db, user, provider))
        return FakeCredential("personal-tavily-key")

    result = await resolve_web_search_api_key(
        "db",
        "user",
        enabled=True,
        provider="tavily",
        resolve_optional_user_api_credentials=resolve_credentials,
    )

    assert result == "personal-tavily-key"
    assert calls == [("db", "user", "tavily")]


@pytest.mark.asyncio
async def test_web_search_api_key_is_empty_without_user_credentials():
    async def resolve_credentials(db, user, provider):
        return None

    result = await resolve_web_search_api_key(
        "db",
        "user",
        enabled=True,
        provider="tavily",
        resolve_optional_user_api_credentials=resolve_credentials,
    )

    assert result is None
