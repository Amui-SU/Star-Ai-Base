import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_ROOT = PROJECT_ROOT / "docs" / "superpowers" / "plans"
INDEX_PATH = PLANS_ROOT / "README.md"
ALLOWED_STATUSES = {"completed", "partial", "superseded", "planned"}
STATUS_PATTERN = re.compile(
    r"^\*\*Status:\*\* (completed|partial|superseded|planned)$", re.MULTILINE
)
INDEX_ROW_PATTERN = re.compile(
    r"^\|\s*\[([^]]+\.md)\]\(([^)]+\.md)\)\s*\|\s*"
    r"(completed|partial|superseded|planned)\s*\|",
    re.MULTILINE,
)


def implementation_plans() -> list[Path]:
    return sorted(path for path in PLANS_ROOT.glob("*.md") if path != INDEX_PATH)


def test_every_plan_has_one_allowed_status():
    missing_or_ambiguous = []
    for path in implementation_plans():
        statuses = STATUS_PATTERN.findall(path.read_text(encoding="utf-8"))
        if len(statuses) != 1 or statuses[0] not in ALLOWED_STATUSES:
            missing_or_ambiguous.append(path.name)

    assert missing_or_ambiguous == []


def test_plan_index_matches_plan_files_and_declared_statuses():
    index = INDEX_PATH.read_text(encoding="utf-8")
    rows = INDEX_ROW_PATTERN.findall(index)
    indexed = {label: (target, status) for label, target, status in rows}
    expected_names = {path.name for path in implementation_plans()}

    assert len(rows) == len(indexed)
    assert set(indexed) == expected_names

    for path in implementation_plans():
        target, indexed_status = indexed[path.name]
        declared_status = STATUS_PATTERN.findall(path.read_text(encoding="utf-8"))[0]
        assert target == path.name
        assert indexed_status == declared_status


def test_completed_plans_have_no_unchecked_steps():
    incomplete = []
    for path in implementation_plans():
        text = path.read_text(encoding="utf-8")
        if STATUS_PATTERN.findall(text) == ["completed"] and re.search(
            r"^\s*- \[ \]", text, re.MULTILINE
        ):
            incomplete.append(path.name)

    assert incomplete == []


def test_superseded_plans_name_an_existing_replacement():
    for path in implementation_plans():
        text = path.read_text(encoding="utf-8")
        if STATUS_PATTERN.findall(text) != ["superseded"]:
            continue

        match = re.search(
            r"^\*\*Superseded by:\*\* \[([^]]+\.md)\]", text, re.MULTILINE
        )
        assert match is not None, path.name
        assert (PLANS_ROOT / match.group(1)).is_file(), path.name
