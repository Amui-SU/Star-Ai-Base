from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_brace_expansion_exception_is_documented_and_time_bounded():
    policy = (
        PROJECT_ROOT / "docs" / "security" / "dependency-audit-exceptions.md"
    ).read_text(encoding="utf-8")

    for required in [
        "GHSA-mh99-v99m-4gvg",
        "development-only",
        "2026-08-11",
        "npm audit --omit=dev --audit-level=high",
    ]:
        assert required in policy
