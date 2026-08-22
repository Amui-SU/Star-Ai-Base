# CI Release Blockers Design

## Goal

Restore the release branch's required CI checks without weakening security
policy, bypassing tests, or broadening the dependency update beyond the
packages required to remove the current production audit failures.

## Observed Failures

Commit `18828b9a41ea90dbba6ef56f7f573f3f694acc06` failed both the push and
pull-request CI runs.

The backend job fails on Linux PowerShell before the fast-workflow assertions
can exercise their intended behavior. PowerShell variables are
case-insensitive, so assigning repository variable `$isWindows` attempts to
overwrite PowerShell Core's read-only automatic `$IsWindows` variable. The
first failure occurs in `scripts/verify-fast.ps1`; the same unsafe name is also
present in `scripts/verify-staged.ps1` and `scripts/worktree-deps.ps1`.

The frontend job stops at the mandatory production dependency audit. The
committed lockfile resolves vulnerable transitive versions of
`brace-expansion` and `nanoid`, and
`npm audit --omit=dev --audit-level=high` exits nonzero. Because the audit is a
required release guard, the workflow must not ignore or conditionally bypass
the result.

## PowerShell Portability Fix

Rename the repository-owned platform flag to `$runningOnWindows` in all three
affected scripts:

- `scripts/verify-fast.ps1`
- `scripts/verify-staged.ps1`
- `scripts/worktree-deps.ps1`

Every read of the old local flag changes with its declaration. No behavior,
path comparison, executable suffix, or junction rule changes beyond avoiding
the automatic-variable collision.

A focused developer-workflow contract scans these scripts and rejects an
assignment to `$isWindows` with case-insensitive matching. Existing subprocess
tests remain the behavioral proof that the scripts continue to enforce target,
staging, and worktree boundaries. The Linux CI backend suite is the final
cross-platform execution proof.

## Dependency Remediation

Use the repository baseline Node `22.13.1` and npm `10.9.2`. Start from a clean
`npm ci`, then request npm's non-forced lockfile remediation. Accept only
transitive lockfile changes necessary for the audit fixes. Do not change audit
severity, add an exception, remove the audit step, or use `--force` merely to
make CI green.

The required dependency acceptance checks are:

```powershell
npm ci --no-audit --no-fund
npm ls --depth=0 --json
npm audit --omit=dev --audit-level=high
```

The audit must exit zero. The dependency tree must have no `problems`. If npm
cannot remediate both production findings without a manifest or direct
dependency change, stop and reassess the smallest compatible upgrade rather
than applying a forced major update.

## Verification And Integration

Implementation occurs in an isolated worktree. TDD first adds a focused guard
that fails on the existing PowerShell declarations, then applies the minimal
rename. Dependency changes are verified from a clean install using npm 10.9.2.

Before integration, run the focused workflow tests, the repository's complete
commit verification, the full backend suite, frontend tests, lint, and the
production build. Fast-forward merge into
`release/video-security-integration-20260729`, repeat the focused checks on the
merged branch, push without force, and monitor both the push and pull-request
CI runs to completion.

CI success means `Changes`, `Backend`, `Frontend`, and `CI Success` all finish
successfully for the pushed commit. A skipped, cancelled, or failed required
job is not success. Pull request 7 remains a draft after CI turns green; this
task does not merge it into `main`.

## Out Of Scope

- Lowering or bypassing the production audit policy.
- Broad dependency modernization unrelated to the reported advisories.
- Fixing development-only audit findings that do not block the production
  audit, unless they are removed by the same non-forced lockfile resolution.
- Redesigning the fast or staged verification workflows.
- Eliminating duplicate push and pull-request workflow runs.
- Marking pull request 7 ready or merging it into `main`.
