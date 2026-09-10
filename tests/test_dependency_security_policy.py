import re
from datetime import date
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def assert_dependency_exception_policy(policy: str) -> None:
    sections = re.split(r"(?m)^#{2,3} ", policy)[1:]
    for section in sections:
        if "- Status: active" not in section:
            continue
        review_date_match = re.search(
            r"Review no later than:\s*(\d{4}-\d{2}-\d{2})", section
        )
        assert review_date_match
        assert date.today() <= date.fromisoformat(review_date_match.group(1))
        assert "- Removal criteria:" in section


def read_dependency_exception_policy() -> str:
    return (
        PROJECT_ROOT / "docs" / "security" / "dependency-audit-exceptions.md"
    ).read_text(encoding="utf-8")


def test_dependency_exceptions_are_current_or_closed():
    policy = read_dependency_exception_policy()

    assert_dependency_exception_policy(policy)
    assert "- Status: active" not in policy
    assert "GHSA-mh99-v99m-4gvg" in policy
    assert "- Status: closed" in policy


def test_active_dependency_exception_rejects_missing_lifecycle_fields():
    policy = read_dependency_exception_policy()
    invalid_policy = policy + "\n## GHSA-test\n\n- Status: active\n"

    with pytest.raises(AssertionError):
        assert_dependency_exception_policy(invalid_policy)
