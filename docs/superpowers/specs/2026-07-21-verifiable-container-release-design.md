# Verifiable Container Release Design

## Objective

Make every manual production release prove that the backend container, frontend
container, local endpoints, public endpoints, and deployment records all refer
to the same tested 40-character Git commit SHA. Preserve the existing manual
ECS approval gate and exact-SHA deployment model.

## Problem Statement

The current release process verifies that SHA-tagged images exist and that the
deployed services return successful HTTP responses. It does not prove that the
public frontend or backend belongs to the requested commit. An operator can
therefore deploy a valid but obsolete SHA, receive a successful health check,
and still see unchanged application behavior.

The observed failure had all of these properties:

- the intended release was `5b5c19259cc6b1482cff507231902a879e763468`;
- the deployment command used `5e362dd60ebbf38c8a2fd1a1630fbac317f9b3e1`;
- `deploy/current-version`, both container image references, and the public
  frontend bundle all remained on the older release;
- the deploy script reported success because availability checks passed.

## Constraints

- Production deployment remains a manual operation on ECS.
- Releases continue to use exact 40-character SHA tags, never `latest`.
- Backend and frontend must always use the same SHA.
- Existing transaction recovery, backup, rollback, disk-capacity checks, and
  environment preflight behavior remain intact.
- Production secrets remain on ECS and are never added to version responses,
  logs, workflow summaries, or repository files.
- A release workflow publishes images but does not imply that ECS was updated.

## Architecture

### Build-time version identity

`Publish Images` passes the tested commit SHA into both image builds.

- The backend image receives `APP_VERSION=<SHA>` as a build/runtime default.
- The frontend image receives `APP_VERSION=<SHA>` in addition to
  `NEXT_PUBLIC_API_URL`.
- The frontend build creates `/version.json` in the static output with exactly:

  ```json
  { "version": "<40-character-sha>" }
  ```

The SHA image tag and OCI `org.opencontainers.image.revision` annotation remain
the registry-level identity. The version endpoints provide runtime and public
routing identity.

### Runtime version endpoints

The backend `/health` response becomes:

```json
{ "status": "healthy", "version": "<40-character-sha>" }
```

The backend reads `APP_VERSION` from configuration and validates production
values as a lowercase 40-character hexadecimal SHA. Local development may use
an explicit non-production fallback such as `development`, but production
preflight and deployment require the exact SHA.

The frontend Nginx container serves the generated `/version.json` as an
ordinary static file. It contains no environment values other than the commit
SHA.

### Compose propagation

`compose.production.yml` passes `APP_VERSION=${IMAGE_TAG}` to the backend. The
frontend version file is baked into its SHA-tagged image during publication.
Both mechanisms derive from the same tested workflow SHA.

## Deployment Flow

Given target SHA `T`, the deployment script performs the existing preflight,
image pulls, backup, and service startup, then verifies these boundaries:

1. backend container image reference ends in `:T`;
2. frontend container image reference ends in `:T`;
3. `http://127.0.0.1:8000/health` returns status `healthy` and version `T`;
4. `http://127.0.0.1:3000/version.json` returns version `T`;
5. `${PUBLIC_BASE_URL}/health` returns status `healthy` and version `T`;
6. `${PUBLIC_BASE_URL}/version.json` returns version `T`.

Only after all six checks pass does the script atomically write `T` to
`deploy/current-version`, update `deploy/previous-version`, clear the
transaction marker, and report success.

This sequence detects a stale frontend container, an incorrect backend image,
an Nginx upstream pointing at another service, or a public route serving a
different deployment.

## Same-version Redeployment

When `T` already equals `deploy/current-version`, deployment stops before image
pulls or runtime mutation with this actionable error:

```text
target SHA is already current; use --allow-redeploy only for an intentional redeploy
```

An operator may explicitly redeploy the same image with:

```bash
./scripts/deploy.sh --allow-redeploy T
```

The override does not weaken any preflight, backup, health, version, or rollback
checks. It only permits the same target SHA to enter the normal deployment
path.

## Failure and Rollback Semantics

Missing endpoints, non-200 responses, invalid JSON, missing versions, and SHA
mismatches are deployment failures.

- Failures before runtime mutation leave the current services untouched.
- Failures after service switching use the existing transaction and rollback
  mechanisms.
- Rollback must verify the previous SHA through both local endpoints and both
  public endpoints before it is considered successful.
- `deploy/current-version` remains unchanged until target verification succeeds.
- Failed target state, transaction markers, backups, and safety directories
  remain governed by the existing recovery rules.

## First Deployment and Baseline Adoption

A host with no running backend or frontend may perform a normal first
deployment without a current version.

A host with existing services but no `deploy/current-version` must not accept a
manually guessed SHA. The documented adoption procedure derives the tag from
both running container image references, requires both tags to be identical
40-character SHAs, and records that verified value before a new deployment.
If the tags differ or are not exact SHAs, the operator must resolve the
ambiguous runtime state rather than fabricate a baseline.

## Publish Workflow Summary

After both SHA images are verified, `Publish Images` writes a GitHub Actions
step summary containing:

- the complete tested SHA;
- backend and frontend SHA image references;
- a copyable `./scripts/deploy.sh <SHA>` command;
- an explicit statement that images were published but ECS was not deployed;
- a reminder to verify `/health` and `/version.json` after manual deployment.

The summary is informational. The workflow receives no SSH permissions and
does not modify ECS.

## Documentation Changes

`docs/deployment/container-production.md` will distinguish four procedures:

1. first deployment on an empty host;
2. normal upgrade to a newly published SHA;
3. intentional same-SHA redeployment with `--allow-redeploy`;
4. rollback to `deploy/previous-version`.

It will also document:

- the difference between image publication and ECS deployment;
- why raw Compose commands require `IMAGE_TAG`;
- the safe baseline-adoption procedure for pre-existing services;
- a post-deployment SHA consistency checklist;
- a decision table for unchanged pages that compares deployment records,
  container image tags, local version endpoints, and public version endpoints.

## Testing Strategy

Tests are added before implementation and must demonstrate the following
failures against the current behavior:

- backend health does not yet expose the build SHA;
- the frontend image does not yet generate `/version.json`;
- same-SHA deployment is not rejected;
- the explicit same-SHA override is not recognized;
- version mismatches are not detected locally or publicly;
- rollback does not verify the restored runtime version;
- the publish workflow does not emit a copyable release summary;
- the production guide does not contain the four release procedures and
  version-diagnostic decision table.

Targeted tests cover backend health, Dockerfile and workflow structure,
deployment script behavior, rollback behavior, and documentation contracts.
The final gate runs the repository commit-verification script, including all
backend tests, frontend lint and tests, formatting checks, and the production
frontend build.

## Acceptance Criteria

- A valid new SHA can be deployed and is recorded only after local and public
  version identity is proven.
- A same-SHA deployment stops before mutation unless `--allow-redeploy` is
  supplied.
- A stale frontend, stale backend, or incorrect public Nginx upstream causes
  deployment failure and rollback.
- Operators can copy one exact deployment command from the successful image
  workflow summary.
- The production guide provides unambiguous first deploy, upgrade, redeploy,
  rollback, and unchanged-page diagnostic instructions.
- No production secrets, automatic SSH deployment, or `latest`-based production
  selection are introduced.
