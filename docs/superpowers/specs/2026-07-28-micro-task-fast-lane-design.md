# Micro-task fast lane design (historical)

> **Status:** Superseded on conflict details by V2.
>
> The current policy is the [V2 design](2026-07-29-micro-task-fast-lane-v2-design.md)
> together with `AGENTS.md`; this historical document is retained for its original
> objective and acceptance context only.

## Original objective

The fast lane was introduced to make narrow, low-risk documentation, style, and
local-component fixes quicker to deliver without weakening targeted evidence.
The historical outcome remains useful: task cost should match risk, and small
changes should retain a concise record and a relevant automated or static check.

## Current V2 interface summary

This section records the current interface so this historical design cannot be
read as an alternative workflow. `AGENTS.md` is authoritative if any wording
differs.

- A qualifying task changes at most three production files, is reversible,
  adds no dependency, stays within one frontend or backend boundary, and does
  not change APIs, persisted data, authentication, authorization, or security.
- A micro-task record defaults to `Change`, `Acceptance`, and `Verification`.
  Record a root cause only for a bug, and out-of-scope behavior only when scope
  could easily expand; no independent spec or implementation plan is needed.
- Worktree choice depends on whether target files overlap existing changes or
  verification shares mutable state. An unrelated dirty file by itself does not
  require a worktree.
- A qualifying task supplies at least one relevant `-BackendTest`,
  `-FrontendTest`, `-LintFile`, or `-StaticFile` target to
  `scripts/verify-fast.ps1`. Options accept comma-separated values.
  `-StaticFile` is only for documentation or style files. The verifier examines
  unstaged, staged, and untracked Git states.
- The fast verifier replaces the full format and no-argument verification steps
  for qualified micro tasks. Normal, high-risk, release, and escalated work
  retain full verification.
- A micro task remains an independently committable changeset. A focused commit
  is created only with user authorization or when integration requires it.

## Historical acceptance context

The original implementation introduced targeted frontend tests, frontend lint,
backend tests, and static-file checks, while preserving the full verification
gate for higher-risk and integration work. V2 clarifies the conflicting details
above without changing that safety goal.
