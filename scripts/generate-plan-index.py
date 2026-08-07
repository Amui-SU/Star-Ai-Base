import re
from pathlib import Path

ALLOWED_STATUSES = {"completed", "partial", "superseded", "planned"}
STATUS_PATTERN = re.compile(r"^\*\*Status:\*\* ([a-z]+)$", re.MULTILINE)


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
