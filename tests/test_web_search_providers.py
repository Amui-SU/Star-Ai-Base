import pytest

from app.services.web_search_providers import normalize_search_results


@pytest.mark.asyncio
async def test_provider_result_normalization_filters_unsafe_urls_by_default():
    results = await normalize_search_results(
        [
            {
                "title": "safe",
                "url": "https://example.com/article",
                "snippet": "safe snippet",
            },
            {
                "title": "local",
                "url": "http://localhost/admin",
                "snippet": "unsafe snippet",
            },
            {
                "title": "file",
                "url": "file:///etc/passwd",
                "snippet": "unsafe snippet",
            },
        ],
        max_results=3,
    )

    assert results == [
        {
            "title": "safe",
            "url": "https://example.com/article",
            "snippet": "safe snippet",
        }
    ]
