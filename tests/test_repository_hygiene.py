from pathlib import Path


def test_project_docs_are_not_gitignored():
    project_root = Path(__file__).resolve().parents[1]
    gitignore_lines = (
        (project_root / ".gitignore").read_text(encoding="utf-8").splitlines()
    )
    active_patterns = {
        line.strip()
        for line in gitignore_lines
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "docs/" not in active_patterns
    assert "CLAUDE.md" not in active_patterns
