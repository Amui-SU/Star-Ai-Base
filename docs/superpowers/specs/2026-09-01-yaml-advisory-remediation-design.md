# YAML Development Dependency Advisory Remediation

## Goal

Remove the remaining moderate `yaml` development-dependency advisory without
changing application behavior, broadening dependency updates, weakening audit
gates, or altering the release and deployment boundary of pull request 7.

## Current State And Root Cause

`frontend/package.json` declares exact dev dependency `yaml@2.8.1`. The
application source does not import it; the root declaration pins the version
used by the Vitest/Vite toolchain. On 2026-09-01,
`npm audit --audit-level=high` reports GHSA-48c2-rrv3-qjmp for `yaml` versions
through 2.8.2. Production dependency audit remains clean. npm identifies
2.9.0 as the available fix, but `npm audit fix --force` would cross the exact
declared range and is too broad for this repository.

`yaml@2.9.0` requires Node 14.6 or later, so it is compatible with the
repository engine range (`^20.19.0 || ^22.13.0 || >=24.0.0`) and canonical
Node 22.13.1 baseline. The release exposes no runtime YAML interface whose
behavior should change.

## Dependency Change

Keep `yaml` as a root exact dev dependency and change only its version from
`2.8.1` to `2.9.0`. Regenerate `frontend/package-lock.json` with the pinned
`npm@10.9.2`, preserving all unrelated dependency resolutions. Do not add an
override, widen the version range, run `npm audit fix --force`, or update any
other package.

The implementation must begin by detaching the worktree's shared
`frontend/node_modules` junction. Dependency installation or lockfile mutation
must not run while the worktree dependency state is `shared`. After detach,
prepare isolated dependencies and verify the actual Node/npm versions before
regenerating the lockfile.

## Contract Coverage

Extend `tests/developer_workflow/test_frontend_dependency_contract.py` with an
explicit security-pin contract. It must require `yaml` to equal `2.9.0` in the
manifest root package, the lockfile root package, and the
`node_modules/yaml` lock entry. The test must fail against the 2.8.1 baseline
before either dependency file changes.

This contract protects the remediation from a later lockfile-only downgrade
or accidental range widening. Existing optional-dependency and Node/npm
contracts remain unchanged.

## Verification

The dependency work is accepted only when all of the following hold in the
isolated worktree:

- A fresh `npm ci --no-audit --no-fund` succeeds with npm 10.9.2.
- `npm ls --depth=0 --json` exits zero without a `problems` array, and
  `npm ls yaml --all` resolves only `yaml@2.9.0` for this tree.
- `npm audit --omit=dev --audit-level=high` exits zero with zero production
  vulnerabilities.
- `npm audit --audit-level=high` exits zero with zero vulnerabilities in the
  full tree; no audit exception is added.
- The focused dependency contract and dependency-security policy tests pass.
- The repository's complete `scripts/verify-before-commit.ps1` verification
  passes, including backend tests, frontend tests, lint, and production build.
- Playwright browser tests pass with one worker.
- An independent review finds no Critical or Important issue.

After a clean fast-forward into
`release/video-security-integration-20260729`, repeat the focused dependency
checks, push without force, and require both push and pull-request CI events to
pass `Changes`, `Backend`, `Frontend`, and `CI Success` for the exact final
SHA. Update pull request 7 to remove the resolved `yaml` follow-up. Do not merge
the pull request into `main` and do not deploy production.

## Out Of Scope

- Updating Vitest, Vite, Next.js, Playwright, or other direct/transitive
  dependencies.
- Removing the root `yaml` security pin or replacing it with an npm override.
- Changing audit severity thresholds, CI routing, or exception policy.
- Changing application YAML parsing behavior; the application has no direct
  YAML import in this release.
- Merging pull request 7 into `main`, publishing images from `main`, or
  deploying ECS.
