import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = PROJECT_ROOT / "scripts" / "generate-plan-index.py"

spec = importlib.util.spec_from_file_location("generate_plan_index", GENERATOR_PATH)
assert spec is not None
assert spec.loader is not None
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def test_render_index_sorts_plans_and_uses_declared_statuses(tmp_path):
    plans_root = tmp_path / "plans"
    plans_root.mkdir()
    (plans_root / "2026-02-b.md").write_text(
        "# B\n\n**Status:** completed\n", encoding="utf-8"
    )
    (plans_root / "README.md").write_text(
        "# Index\n\n**Status:** partial\n", encoding="utf-8"
    )
    (plans_root / "2026-01-a.md").write_text(
        "# A\n\n**Status:** planned\n", encoding="utf-8"
    )

    rendered = generator.render_index(plans_root)

    assert rendered == "\n".join(
        [
            "| Plan                         | Status    |",
            "| ---------------------------- | --------- |",
            "| [2026-01-a.md](2026-01-a.md) | planned   |",
            "| [2026-02-b.md](2026-02-b.md) | completed |",
        ]
    )


@pytest.mark.parametrize(
    "contents",
    [
        "# Missing\n",
        "**Status:** planned\n\n**Status:** completed\n",
        "**Status:** abandoned\n",
    ],
    ids=["missing", "duplicate", "unsupported"],
)
def test_extract_status_rejects_invalid_status_fields(tmp_path, contents):
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError):
        generator.extract_status(plan_path)
