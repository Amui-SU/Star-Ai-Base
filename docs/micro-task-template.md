# Micro Task

Use this record in the task description or commit body. A qualifying micro task
does not need an independent design spec or implementation plan.

**Change:**

**Acceptance:**

**Verification:**

Record the actual command, specific targets, and any required manual results. A
bare “verified” is not evidence.

Optional when this is a bug: **Root cause:**

Optional when scope could easily expand: **Out of scope:**

For an isolated worktree that needs frontend dependencies:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/worktree-deps.ps1 -Mode Prepare
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/worktree-deps.ps1 -Mode Status
# Before cleanup:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/worktree-deps.ps1 -Mode Detach
git worktree remove .worktrees/<slice-name>
```

While status is `shared`, do not run `npm install`, `npm ci`, or dependency
update commands. Detach first if either frontend dependency manifest changes.
