from types import SimpleNamespace

from app.services.api_credentials import (
    LLM_API_SOURCE_OFFICIAL,
    LLM_API_SOURCE_PERSONAL,
)
from app.services.chat_config import current_user_llm_source


def test_current_user_llm_source_prefers_saved_source():
    user = SimpleNamespace(llm_api_source=LLM_API_SOURCE_OFFICIAL)

    assert (
        current_user_llm_source(user, has_personal=True, has_official=True)
        == LLM_API_SOURCE_OFFICIAL
    )


def test_current_user_llm_source_falls_back_to_available_credentials():
    user = SimpleNamespace(llm_api_source=None)

    assert (
        current_user_llm_source(user, has_personal=True, has_official=True)
        == LLM_API_SOURCE_PERSONAL
    )
    assert (
        current_user_llm_source(user, has_personal=False, has_official=True)
        == LLM_API_SOURCE_OFFICIAL
    )
    assert (
        current_user_llm_source(user, has_personal=False, has_official=False)
        == LLM_API_SOURCE_PERSONAL
    )
