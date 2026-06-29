from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import get_project_root


def test_web_search_service_delegates_fetch_and_safety_boundaries():
    project_root = get_project_root()
    service_path = project_root / "app/services/web_search.py"
    safety_path = project_root / "app/services/web_search_safety.py"
    fetcher_path = project_root / "app/services/web_page_fetcher.py"
    parsers_path = project_root / "app/services/web_search_parsers.py"
    source = service_path.read_text(encoding="utf-8")
    declared_names = declared_callable_names(source)

    assert safety_path.exists()
    assert fetcher_path.exists()
    assert parsers_path.exists()
    assert "from app.services.web_search_safety import" in source
    assert "from app.services.web_page_fetcher import" in source
    assert "from app.services.web_search_parsers import" in source
    assert len(source.splitlines()) <= 560
    assert declared_names.isdisjoint(
        {
            "_DuckDuckGoResultParser",
            "_SogouResultParser",
            "_YahooResultParser",
            "_ReadableHTMLParser",
            "_is_supported_content_type",
            "_charset_from_content_type",
            "_decode_body",
        }
    )
