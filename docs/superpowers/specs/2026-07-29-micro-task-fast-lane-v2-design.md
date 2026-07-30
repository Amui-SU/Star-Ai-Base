# Micro-task fast lane V2 design

## Goal

Keep verification proportional to risk without allowing a nominal target to
hide unrelated code or configuration changes. `AGENTS.md` is the authoritative
workflow policy; this design records the verifier contract and rationale.

## Verification mapping

- Python production changes require a targeted `-BackendTest`. The verifier
  automatically runs `python -m black --check --` over every scoped changed
  Python file before backend tests, so task records do not claim a separate
  unexecuted Black command.
- JavaScript or TypeScript production changes require `-LintFile` for every
  changed code file. Behavior changes additionally require `-FrontendTest`.
- Documentation and style changes use `-StaticFile` plus any necessary manual
  check. `-StaticFile` supports only Markdown, plain text, CSS, SCSS, and Less.
  HTML, JSON, YAML, and YML require complete verification, even for small
  changes.
- Shared build, deployment, authentication, and security configuration always
  escalates to complete verification.

The `Verification` record contains the actual command, specific targets, and
required manual results. A bare “verified” is not evidence.

## Task changeset scope

In a clean or isolated checkout, omit `-TaskFile`; verification covers all
changed files. With unrelated non-overlapping dirty changes, list every task
file using `-TaskFile` and record the actual command and targets. `-TaskFile`
accepts comma-separated values, is not a verification target, cannot declare an
unchanged file, and cannot contain duplicate or out-of-repository paths. Every
tool target is an existing relative real file inside its required root: options,
absolute paths, traversal, reparse points, symbolic links, and Git mode-120000
entries are rejected. A backend target may append a pytest node id (`::...`) to
an otherwise verified `.py` file.

The explicit scope limits changed-file mapping, tracked unstaged and staged
whitespace checks, and untracked text hygiene to the declared task changeset. It
does not weaken the mapping rules for those files. When target files overlap
existing changes or verification shares mutable state, use a worktree instead
of scoping around the conflict.

```powershell
powershell -File scripts\verify-fast.ps1 `
  -TaskFile AGENTS.md,docs/micro-task-template.md `
  -StaticFile AGENTS.md,docs/micro-task-template.md
```

## Static-file coverage contract

`verify-fast.ps1` collects changed paths from unstaged, staged, and untracked Git
states using NUL-delimited output. Every `-StaticFile` target must belong to that
change set. The mapping applies regardless of other targets: every changed
static file must be named by `-StaticFile`, every changed frontend JavaScript or
TypeScript file must be named by `-LintFile`, and any changed Python file
requires at least one `-BackendTest`. Unsupported changed files require complete
verification.

The allowed extensions are `.md`, `.txt`, `.css`, `.scss`, and `.less`.
Structured and configuration formats are intentionally excluded from the fast
lane rather than classified by filename or presumed intent.

Every in-scope static target is read as strict streaming UTF-8 and must contain
no NUL bytes. Invalid UTF-8 or NUL means the fast lane fails closed and requires
complete verification; unrelated untracked binary files remain outside this
static-file contract.

## Workflow boundaries

Qualified micro tasks use `scripts/verify-fast.ps1` in place of the format and
full no-argument verification steps. Normal tasks, high-risk tasks, releases,
dependency changes, shared build or deployment configuration, authentication,
and security changes retain complete verification.

A micro task remains an independently committable changeset. Create a focused
commit only when authorized by the user or required by integration. Use a
worktree when target files overlap existing changes or verification shares
mutable state, rather than for an unrelated dirty path alone.
