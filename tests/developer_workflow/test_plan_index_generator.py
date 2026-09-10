import importlib.util
import subprocess
import sys
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


def create_plan_fixture(tmp_path):
    plans_root = tmp_path / "plans"
    plans_root.mkdir()
    (plans_root / "2026-01-plan.md").write_text(
        "# Plan\n\n**Status:** planned\n", encoding="utf-8"
    )
    index_path = plans_root / "README.md"
    index_path.write_text(
        "# Index\n\n"
        "<!-- BEGIN GENERATED PLAN INDEX -->\n\n"
        "stale\n\n"
        "<!-- END GENERATED PLAN INDEX -->\n\n"
        "Footer\n",
        encoding="utf-8",
    )
    return plans_root, index_path


def test_replace_generated_region_preserves_surrounding_content(tmp_path):
    plans_root, index_path = create_plan_fixture(tmp_path)
    original = index_path.read_text(encoding="utf-8")

    updated = generator.replace_generated_region(
        original, generator.render_index(plans_root)
    )

    assert updated.startswith("# Index\n\n<!-- BEGIN GENERATED PLAN INDEX -->")
    assert "[2026-01-plan.md](2026-01-plan.md)" in updated
    assert updated.endswith("<!-- END GENERATED PLAN INDEX -->\n\nFooter\n")


@pytest.mark.parametrize(
    "index_text",
    [
        "# Missing markers\n",
        "<!-- BEGIN GENERATED PLAN INDEX -->\n"
        "<!-- BEGIN GENERATED PLAN INDEX -->\n"
        "<!-- END GENERATED PLAN INDEX -->\n",
        "<!-- END GENERATED PLAN INDEX -->\n" "<!-- BEGIN GENERATED PLAN INDEX -->\n",
    ],
    ids=["missing", "duplicate", "out-of-order"],
)
def test_replace_generated_region_rejects_invalid_markers(index_text):
    with pytest.raises(ValueError):
        generator.replace_generated_region(index_text, "| Plan | Status |")


def test_update_index_check_mode_reports_drift_without_writing(tmp_path, capsys):
    plans_root, index_path = create_plan_fixture(tmp_path)
    original = index_path.read_text(encoding="utf-8")

    result = generator.update_index(plans_root, index_path, check=True)

    assert result == 1
    assert index_path.read_text(encoding="utf-8") == original
    assert "python scripts/generate-plan-index.py" in capsys.readouterr().out


def test_update_index_default_mode_writes_generated_content(tmp_path):
    plans_root, index_path = create_plan_fixture(tmp_path)

    result = generator.update_index(plans_root, index_path, check=False)

    assert result == 0
    assert "stale" not in index_path.read_text(encoding="utf-8")


def test_cli_check_accepts_committed_index():
    result = subprocess.run(
        [sys.executable, str(GENERATOR_PATH), "--check"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
