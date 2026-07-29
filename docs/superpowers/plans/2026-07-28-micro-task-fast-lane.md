# Micro-task Fast Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a risk-based fast lane for micro-tasks with concise documentation and targeted verification.

**Architecture:** Project policy in `AGENTS.md` classifies work before execution. A focused PowerShell wrapper runs only explicitly selected checks, while a small pytest structure guard prevents the fast lane from expanding into or replacing full verification.

**Tech Stack:** Markdown, PowerShell, pytest, npm, Vitest, ESLint

---

### Task 1: Lock the workflow contract

**Files:**

- Create: `tests/test_fast_workflow.py`

- [x] Write tests requiring the fast-lane section, task template, script parameters, targeted commands, and full-verification boundary.
- [x] Run `python -m pytest -q tests/test_fast_workflow.py` and confirm failure because the files and policy do not exist.

### Task 2: Document task classification

**Files:**

- Modify: `AGENTS.md`
- Create: `docs/micro-task-template.md`

- [x] Add micro, normal, and high-risk classification before the worktree rules.
- [x] Define direct-work and escalation conditions without weakening release or security verification.
- [x] Add the six-field reusable micro-task template.

### Task 3: Implement targeted verification

**Files:**

- Create: `scripts/verify-fast.ps1`

- [x] Accept `FrontendTest`, `LintFile`, and `BackendTest` arrays.
- [x] Resolve commands from the repository root and `frontend/` without requiring callers to change directory.
- [x] Always run `git diff --check`, reject an empty target set, and stop on the first failed command.
- [x] Run `python -m pytest -q tests/test_fast_workflow.py` and confirm it passes.

### Task 4: Verify and integrate

**Files:**

- Verify all files above.

- [x] Run the fast script against `tests/test_fast_workflow.py`.
- [x] Run `python -m pytest -q tests/test_fast_workflow.py tests/test_dev_script_boundaries.py`.
- [x] Run `git diff --check` and review the complete diff.
- [x] Commit the focused change; integrate it without disturbing unrelated working-tree changes.
