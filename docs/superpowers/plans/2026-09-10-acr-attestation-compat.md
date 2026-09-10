# ACR Attestation Compatibility Implementation Plan

**Status:** completed

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Restore ACR publication without removing provenance or SHA safeguards.

**Architecture:** Explicitly select the legacy attestation envelope in both existing image exporters. Keep all publication gates unchanged.

**Tech Stack:** GitHub Actions, Docker Buildx/BuildKit, pytest, PyYAML.

**Spec:** ../specs/2026-09-10-acr-attestation-compat-design.md

## Global Constraints

- Both exporters use `type=image,oci-mediatypes=true,oci-artifact=false`.
- Preserve provenance, `push: true`, immutable-by-workflow SHA handling, revision annotations and verification.
- No ECS deployment, credentials changes, or deletion/overwrite of SHA tags.
- Work from main in `.worktrees/acr-attestation-compat`; do not install into shared dependencies.
- Full verification and normal hooks precede commit; exact-SHA CI and publication are release acceptance gates.

## Task 1: Compatible exporters and regression coverage

**Files:** `.github/workflows/publish-images.yml`, `tests/test_ci_workflow.py`, `docs/deployment/container-production.md`, this plan/spec and generated `docs/superpowers/plans/README.md`.

**Interface:** Existing docker/build-push-action `with.outputs` input; no application API changes.

- [x] Run baseline `python -m pytest -q tests/test_ci_workflow.py`.
- [x] Add a parameterized test selecting each build action from parsed YAML and asserting one image exporter with `oci-artifact=false`, `oci-mediatypes=true`, push enabled, and provenance not disabled. Parse comma-separated key/value attributes rather than search source text.

  ```python
  exporters = [dict(field.split("=", 1) for field in line.split(","))
               for line in inputs.get("outputs", "").splitlines() if line.strip()]
  assert len(exporters) == 1
  assert exporters[0]["oci-artifact"] == "false"
  ```

- [x] Run `python -m pytest -q tests/test_ci_workflow.py -k legacy_attestation`; expect two failures because outputs are absent.
- [x] Add to both build steps:

  ```yaml
  outputs: type=image,oci-mediatypes=true,oci-artifact=false
  ```

- [x] Document the compatibility reason, preserved provenance, and unchanged release safeguards.
- [x] Run the complete workflow test file and plan/index tests; verify whitespace.
- [x] Run `scripts/verify-before-commit.ps1 -Format` and complete verification with durable logs. A local Docker daemon is not available; real registry compatibility is accepted only by GitHub publication.
- [x] Review the diff, commit explicitly scoped files with normal hooks, and push the focused branch for CI/review.
- [x] After authorized integration, verify main CI and Publish Images for the exact new commit. Record results; no production deployment.

## Execution record

Design approved in chat on 2026-09-10. Base is
`9228693785d5ac0ee668535bc98a0d545b77d7a3`. The worktree shares unchanged frontend
dependencies. Local Docker CLI exists but its Linux-engine named pipe is absent;
no daemon or system configuration was changed.

Baseline workflow tests passed 34 cases. The two new exporter cases failed
because each build action lacked an explicit exporter, then the workflow and
plan/index regression command passed 52 tests after the change. Black,
Prettier, and whitespace checks passed. Independent read-only review found no
Critical, Important, or actionable Minor issues. Full verification exited 0:
1594 backend tests passed, 6 skipped, and 2 existing httpx warnings; all 410
frontend tests passed, along with Black, Prettier, lint, TypeScript and the
production build. Its durable output is
`.pytest_cache/acr-attestation-full-verification.log`. This is local acceptance
only; the subsequent exact-SHA release evidence is recorded below.

## Completion record (2026-09-11)

Implementation commit `b52a30046239f44104426d04e74468d078f1b52b` passed normal
hooks and [PR CI 34500146719](https://github.com/Amui-SU/Star-Ai-Base/actions/runs/34500146719).
[PR 8](https://github.com/Amui-SU/Star-Ai-Base/pull/8) merged as
`794440a611a5ee3c30a9f1da78f121ee5a3fb84a`; the merged tree is identical to
the locally verified implementation.

For that exact merge SHA, [main CI 34500892335](https://github.com/Amui-SU/Star-Ai-Base/actions/runs/34500892335)
and [Publish Images 34501562886](https://github.com/Amui-SU/Star-Ai-Base/actions/runs/34501562886)
both succeeded. Backend and frontend publication, both SHA revision checks,
and the manual deployment summary completed successfully. This proves ACR
accepted both images with the compatible attestation envelope. No provenance,
SHA guard, credentials, registry permissions, or production service was changed.
ECS was not deployed. This completion record is documentation-only and does not
change the verified compatibility implementation.
