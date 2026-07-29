# Micro-task fast lane V2 design

## Goal

Keep verification proportional to risk without allowing a nominal target to
hide unrelated code or configuration changes. `AGENTS.md` is the authoritative
workflow policy; this design records the verifier contract and rationale.

## Verification mapping

- Python production changes require a targeted `-BackendTest` and a Black check
  covering all changed Python files.
- JavaScript or TypeScript production changes require `-LintFile` for every
  changed code file. Behavior changes additionally require `-FrontendTest`.
- Documentation and style changes use `-StaticFile` plus any necessary manual
  check. HTML, JSON, YAML, or YML are eligible only as pure non-behavioral static
  content.
- Shared build, deployment, authentication, and security configuration always
  escalates to complete verification.

The `Verification` record contains the actual command, specific targets, and
required manual results. A bare “verified” is not evidence.

## Static-file coverage contract

`verify-fast.ps1` collects changed paths from unstaged, staged, and untracked Git
states using NUL-delimited output. Every `-StaticFile` target must belong to that
change set. The mapping applies regardless of other targets: every changed
static file must be named by `-StaticFile`, every changed frontend JavaScript or
TypeScript file must be named by `-LintFile`, and any changed Python file
requires at least one `-BackendTest`. Unsupported changed files require complete
verification.

The allowed extensions remain Markdown, plain text, CSS, SCSS, Less, HTML,
JSON, YAML, and YML. Extension eligibility does not reclassify behavioral or
high-risk configuration as static content.

## Workflow boundaries

Qualified micro tasks use `scripts/verify-fast.ps1` in place of the format and
full no-argument verification steps. Normal tasks, high-risk tasks, releases,
dependency changes, shared build or deployment configuration, authentication,
and security changes retain complete verification.

A micro task remains an independently committable changeset. Create a focused
commit only when authorized by the user or required by integration. Use a
worktree when target files overlap existing changes or verification shares
mutable state, rather than for an unrelated dirty path alone.
