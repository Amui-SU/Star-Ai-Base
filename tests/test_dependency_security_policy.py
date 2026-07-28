import re
from datetime import date
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def assert_brace_expansion_exception_policy(policy: str) -> None:
    for required in [
        "GHSA-mh99-v99m-4gvg",
        "development-only",
        "2026-08-11",
        "npm audit --omit=dev --audit-level=high",
    ]:
        assert required in policy

    review_date_match = re.search(
        r"Review no later than:\s*(\d{4}-\d{2}-\d{2})", policy
    )
    assert review_date_match
    assert date.today() <= date.fromisoformat(review_date_match.group(1))

    removal_marker = "- Removal criteria:"
    assert removal_marker in policy
    removal_criteria = policy.split(removal_marker, 1)[1]
    assert "npm audit --audit-level=high" in removal_criteria


def read_dependency_exception_policy() -> str:
    return (
        PROJECT_ROOT / "docs" / "security" / "dependency-audit-exceptions.md"
    ).read_text(encoding="utf-8")


def test_brace_expansion_exception_is_documented_and_time_bounded():
    assert_brace_expansion_exception_policy(read_dependency_exception_policy())


def test_brace_expansion_exception_rejects_missing_removal_criteria():
    policy = read_dependency_exception_policy()
    policy_without_removal_criteria = policy.split("- Removal criteria:", 1)[0]

    with pytest.raises(AssertionError):
        assert_brace_expansion_exception_policy(policy_without_removal_criteria)
