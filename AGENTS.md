# Codex Project Instructions

## Stable Commit Workflow

Before creating a git commit in this repository, run the commit checks in this order.

1. Inspect the worktree:

   ```powershell
   git status --short
   git diff --check
   ```

2. Format changed files before committing:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format
   ```

3. Run verification:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1
   ```

4. Stage files explicitly. Do not stage local secrets, generated data, or build/cache output:

   - `.env.local`
   - `data/`
   - `logs/`
   - `frontend/.next/`
   - `frontend/out/`
   - `frontend/node_modules/`
   - `frontend/android/**/build/`
   - `__pycache__/`
   - `.pytest_cache/`

5. After staging, run:

   ```powershell
   git diff --cached --check
   git diff --cached --name-only
   ```

6. Commit normally and let the pre-commit hook run. If the hook fails, read the failure and fix formatting or tests first. Do not skip hooks unless the hook itself is demonstrably wrong and equivalent checks have already passed.

7. After commit, verify:

   ```powershell
   git log -1 --oneline
   git status --short
   ```

## Expected Checks

The local verification script runs:

- Python formatting check with Black.
- Backend tests with `python -m pytest -q`.
- Frontend Prettier checks for staged/changing web files.
- Frontend `npm run lint`.
- Frontend tests.
- Frontend production build.
- Git whitespace checks.

For risky or broad changes, prefer the full verification path even if only a few files changed.
