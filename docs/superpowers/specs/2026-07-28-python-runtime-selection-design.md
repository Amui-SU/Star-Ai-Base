# Python Runtime Selection Design

## Goal

Make `scripts/dev.ps1` reliably start the backend when multiple Python installations exist, and fail quickly with actionable diagnostics when no interpreter can load the application.

## Root Cause

The startup script chooses the first runnable interpreter. On this machine it prefers `C:\ProgramData\anaconda3\envs\bilibili-rag\python.exe`, which can execute Python and import the small dependency probe but cannot import `app.main` because `anthropic` is missing. `doctor` therefore reports a false healthy state, while `start` launches a backend process that exits immediately and then waits the full 60-second port timeout.

The worktree and main checkout share system Python installations, so the failure is not isolated by Git worktrees.

## Design

### Candidate selection

Keep the existing candidate order: project `.venv`, project `venv`, configured `BILIBILI_RAG_PYTHON`, known Conda environment, then `python` from `PATH`.

For `doctor` and `start`, select the first candidate that is runnable and can import the real application entry point from the target project root:

```python
import app.main
```

This exact import probe follows the application's runtime dependency graph and automatically detects future missing imports without maintaining a second package list.

For `install`, select the first runnable candidate without requiring application imports, so an incomplete configured environment can still be repaired.

### Diagnostics

Record a concise failure reason for each runnable candidate that cannot import the application. `doctor` reports which interpreter was rejected and why, then reports the healthy interpreter it selected. If no candidate is healthy, `doctor` and `start` instruct the user to run `install` or set `BILIBILI_RAG_PYTHON`.

### Fast startup failure

While waiting for ports 8000 and 3000, also monitor the corresponding child process. If it exits before the port listens, stop waiting immediately, show the relevant logs, and raise an error that includes the process exit code.

### Runtime metadata

Persist the actual selected Python executable in `logs/runtime.json`. `status` should continue reading this metadata; it does not need to reselect the interpreter used by an already-running process.

## Testing

Add PowerShell-facing structure or behavior tests that verify:

- an incomplete earlier candidate is skipped in favor of a later healthy candidate;
- install mode can still select a runnable but incomplete interpreter;
- a child process that exits early causes the wait helper to return immediately;
- the real worktree starts successfully without a temporary environment override;
- backend and frontend health endpoints return HTTP 200.

## Non-goals

- Installing packages automatically during `start`.
- Changing global or user environment variables.
- Managing Conda environments.
- Changing backend application imports or making `anthropic` optional.
