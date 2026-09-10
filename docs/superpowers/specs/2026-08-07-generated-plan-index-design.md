# Generated Plan Index Design

## Goal

Remove duplicate manual maintenance from the implementation-plan index while
keeping the index readable in the repository and verifiable in CI.

## Source Of Truth

Each implementation plan's single `**Status:**` field remains authoritative.
`docs/superpowers/plans/README.md` becomes a generated view of those fields,
not a second status source.

The generated table contains only `Plan` and `Status`. The current `Notes`
column is removed because its free-form text cannot be derived reliably and
would preserve the same manual synchronization cost. Superseded plans continue
to name their replacements inside their own documents.

## Generator

Add `scripts/generate-plan-index.py` with two deterministic modes:

- the default mode scans `docs/superpowers/plans/*.md`, excluding `README.md`,
  sorts files by name, and rewrites the generated table;
- `--check` renders the expected table without writing and exits nonzero with
  the exact update command when the committed index is stale.

The README contains explicit begin and end comments around the generated
region. The generator replaces only that region so the lifecycle explanation
and status definitions remain hand-maintained documentation. Output uses UTF-8,
LF line endings, stable Markdown formatting, and repository-relative links.

The generator rejects a plan with a missing, duplicate, or unsupported status
instead of producing a partial index. It also fails clearly when either README
marker is missing or duplicated.

## Verification Integration

`tests/developer_workflow/test_plan_lifecycle.py` exercises status parsing,
deterministic rendering, marker replacement, and stale-index detection through
the generator's public functions and command-line entry point. The existing
lifecycle assertions continue to guard completed and superseded plans.

The normal backend test suite already runs this developer-workflow test in CI,
so no new CI job or pre-commit mutation is required. Developers update the
index explicitly with:

```powershell
python scripts/generate-plan-index.py
```

Commit and CI checks use:

```powershell
python scripts/generate-plan-index.py --check
```

This avoids silently changing staged files and does not introduce another file
association or shell-opening path in the pre-commit hook.

## Out Of Scope

- Automatically rewriting the index during pre-commit.
- Generating or changing plan statuses.
- Rewriting historical plan content or checklist state.
- Adding dependencies or changing application runtime behavior.
- Publishing or deploying after the release branch is pushed.
