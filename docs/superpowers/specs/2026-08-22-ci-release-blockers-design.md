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

Local complete verification also exposes an expired development-dependency
exception for `GHSA-mh99-v99m-4gvg`. The same non-forced lockfile remediation
resolves patched `brace-expansion` versions for the development tree, and the
full high-severity audit now exits successfully.

## PowerShell Portability Fix

Rename the repository-owned platform flag to `$runningOnWindows` in all three
affected scripts:

- `scripts/verify-fast.ps1`
- `scripts/verify-staged.ps1`
- `scripts/worktree-deps.ps1`

Every read of the old local flag changes with its declaration. No behavior,
path comparison, executable suffix, or junction rule changes beyond avoiding
the automatic-variable collision.

Existing subprocess tests execute all three scripts with PowerShell Core and
already fail on the automatic-variable collision. Those tests are the focused
behavioral contract: they must pass after the rename while continuing to enforce
target, staging, and worktree boundaries. The Linux CI backend suite is the
final cross-platform execution proof.

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
npm audit --audit-level=high
```

The audit must exit zero. The dependency tree must have no `problems`. If npm
cannot remediate both production findings without a manifest or direct
dependency change, stop and reassess the smallest compatible upgrade rather
than applying a forced major update.

Because the full high-severity audit passes after the lockfile update, close
the expired `GHSA-mh99-v99m-4gvg` exception with a dated resolution record and
remove `continue-on-error` from the full audit CI step. Generic policy tests
continue to reject active exceptions that lack a review deadline or removal
criteria.

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

## Linux Suite Follow-Up

The first post-fix remote runs (`32577837180` push and `32577838401` pull
request) confirmed the complete frontend path but exposed 50 additional backend
test failures after the automatic-variable collision was removed. The failures
are test-environment contracts rather than application behavior regressions:

- the Windows ACL/kernel32 hook installer suite was not marked Windows-only;
- POSIX hook tests assumed the Windows `python` executable name and an isolated
  PowerShell lookup despite retaining system tools on `PATH`;
- CI installed runtime requirements but not the Black formatter exercised by
  fast-workflow subprocess tests;
- Windows-only process-tree unit branches referenced Windows subprocess
  constants while running on Linux;
- the staged verifier rejected the normal symbolic-link chain used by hosted
  POSIX Python installations; and
- one traversal test asserted a later containment error even though the script
  rejects `..` earlier.

Keep cross-platform hook and verifier behavior covered. Skip only the installer
module whose production implementation explicitly depends on Windows ACLs and
kernel32. Install pinned developer tooling through a separate
`requirements-dev.txt`, preserve runtime-only `requirements.txt` for deployment,
and limit executable reparse-path enforcement to Windows.

## Out Of Scope

- Lowering or bypassing the production audit policy.
- Broad dependency modernization unrelated to the reported advisories.
- Broad development-dependency upgrades beyond patches selected by the same
  non-forced lockfile remediation.
- Redesigning the fast or staged verification workflows.
- Eliminating duplicate push and pull-request workflow runs.
- Marking pull request 7 ready or merging it into `main`.
