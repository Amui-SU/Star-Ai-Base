import argparse
import re
import sys
from pathlib import Path

ALLOWED_STATUSES = {"completed", "partial", "superseded", "planned"}
STATUS_PATTERN = re.compile(r"^\*\*Status:\*\* ([a-z]+)$", re.MULTILINE)
GENERATED_START = "<!-- BEGIN GENERATED PLAN INDEX -->"
GENERATED_END = "<!-- END GENERATED PLAN INDEX -->"


def extract_status(path: Path) -> str:
    statuses = STATUS_PATTERN.findall(path.read_text(encoding="utf-8"))
    if len(statuses) != 1 or statuses[0] not in ALLOWED_STATUSES:
        raise ValueError(f"{path.name}: expected exactly one allowed **Status:** field")
    return statuses[0]


def render_index(plans_root: Path) -> str:
    plans = sorted(path for path in plans_root.glob("*.md") if path.name != "README.md")
    rows = [(f"[{path.name}]({path.name})", extract_status(path)) for path in plans]
    plan_width = max([len("Plan"), *(len(plan) for plan, _ in rows)])
    status_width = max([len("Status"), *(len(status) for _, status in rows)])
    lines = [
        f"| {'Plan':<{plan_width}} | {'Status':<{status_width}} |",
        f"| {'-' * plan_width} | {'-' * status_width} |",
    ]
    lines.extend(
        f"| {plan:<{plan_width}} | {status:<{status_width}} |" for plan, status in rows
    )
    return "\n".join(lines)


def replace_generated_region(index_text: str, rendered: str) -> str:
    if index_text.count(GENERATED_START) != 1 or index_text.count(GENERATED_END) != 1:
        raise ValueError("README must contain exactly one generated index marker pair")

    start = index_text.index(GENERATED_START) + len(GENERATED_START)
    end = index_text.index(GENERATED_END)
    if start >= end:
        raise ValueError("generated index markers are out of order")

    return f"{index_text[:start]}\n\n{rendered}\n\n{index_text[end:]}"


def update_index(plans_root: Path, index_path: Path, check: bool) -> int:
    current = index_path.read_text(encoding="utf-8")
    expected = replace_generated_region(current, render_index(plans_root))
    if expected == current:
        return 0
    if check:
        print("Plan index is stale. Run: python scripts/generate-plan-index.py")
        return 1

    index_path.write_text(expected, encoding="utf-8", newline="\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the implementation-plan index."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report index drift without changing README.md",
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    plans_root = project_root / "docs" / "superpowers" / "plans"
    index_path = plans_root / "README.md"

    try:
        return update_index(plans_root, index_path, check=args.check)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
