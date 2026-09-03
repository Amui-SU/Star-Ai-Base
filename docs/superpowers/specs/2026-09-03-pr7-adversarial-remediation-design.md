# PR 7 Adversarial Remediation Design

## Goal

Close the six merge-blocking findings from the final adversarial review of pull
request 7 without weakening authentication, workspace isolation, CI, or release
boundaries. The remediation must preserve existing public API payloads except
that failed password-reset email delivery becomes indistinguishable from every
other accepted send request.

The work is delivered in two independently reviewable batches. Batch 1 hardens
authentication and gateway rate limiting. Batch 2 prevents frontend stale-state
loss and unbounded polling and makes path-aware CI fail closed for unrecognized
documents.

## Current Failure Modes

### Password reset enumeration

The password-reset send endpoint returns the generic 200 response for an
unknown or inactive account but returns 500 when an active account's SMTP
delivery fails. During an SMTP outage or recipient rejection, response status
therefore reveals whether an active account exists.

### Login versus credential change

Password login validates the old password before inserting a session. A
concurrent reset can update the password and revoke all sessions before that
insert commits. The late login then creates a session that remains accepted
despite having authenticated with the old password.

### AI response versus manual note editing

The AI editing hook closes over the blocks from the render that started the
request. If the user edits while the request is pending, applying the response
rebuilds the note from the stale snapshot and records the stale snapshot for
undo, silently discarding the intervening edit.

### Unbounded task status polling

Task status requests have no request timeout. A permanently pending transport
can occupy an in-flight slot forever, while HTTP 401, 403, or 404 responses and
repeated transport failures are retried every two seconds without a terminal
state. Closing the import dialog intentionally does not stop background
tracking, so the leak survives dialog closure.

### CI document routing

The classifier treats every unrecognized `.md`, `.txt`, or `.rst` file as
documentation-only. Security exception files, ordinary design specifications,
deployment documents, and unknown root documents can consequently skip the
tests that enforce their policies, contradicting the repository's
`unknown-policy-paths=backend+frontend` contract.

### Password-reset burst limiting

The production Nginx example applies its send-code zone only to the registration
endpoint. The application fallback performs select-then-increment, so concurrent
requests can lose increments and exceed the intended three-request window.

## Batch 1: Authentication And Gateway Security

### Uniform reset-send response

`send_password_reset_code` continues to reserve a code before delivery. If
delivery fails, it deletes only the reservation it created and commits that
cleanup, logs the failure without the code or password, and returns the same
generic 200 payload used for unknown, inactive, duplicate-active-code, and
successful requests. Invalid email and rate-limit failures remain 400 and 429
because they describe request validity and client behavior rather than account
existence.

Debug mode retains the existing response shape. A debug code for an unknown
account remains unusable and is never persisted. No production response may
expose SMTP success, account state, a stored code hash, or delivery diagnostics.

### Credential-version session invalidation

Add non-null integer `credential_version` columns with default `0` to
`SystemUser` and `SystemSession`. New sessions copy the version observed on the
authenticated user. Both current-user resolution paths load the session and
active user together and reject a session whose version differs from the
user's current version.

Self-service reset atomically increments the user's credential version in the
same transaction as the password update, reset-code consumption, and revocation
of currently visible sessions. Admin password reset also increments the version
before deleting sessions. OAuth and registration sessions store the current
version. This provides the required ordering:

- A session committed before a reset is revoked by that reset.
- A login that verified the old password but commits after the reset stores the
  old version and is rejected on first use.
- Existing databases and sessions migrate with version `0`, so sessions remain
  valid until the next credential change.

SQLite legacy schema maintenance adds both columns as
`INTEGER NOT NULL DEFAULT 0`. New-table metadata uses matching server and Python
defaults. Migration and session tests must cover legacy rows, normal login,
OAuth session creation, admin reset, self-service reset, and the login/reset
interleaving with independent database sessions.

### Atomic IP rate limiting and Nginx coverage

Replace read-modify-write counting with a database-side conditional update.
For an existing IP, one UPDATE resets an expired window to count 1 or increments
an active window only while its count is below the limit. Its returned row is
the allow decision. If no row is returned, distinguish a blocked existing row
from a missing row; insert a missing row, and on a unique-key race roll back the
savepoint and retry the decision. Bound retries and fail closed if contention
cannot be resolved.

The Nginx example uses one exact regular-expression location for both
`/system-auth/send-code` and `/system-auth/password-reset/send-code`, with an
optional trailing slash, the same zone, burst, 429 response, proxy headers, and
timeouts. The generic `/system-auth` proxy remains the fallback for other
authentication endpoints. A configuration contract test must exercise both
paths and reject accidental omission of either one.

## Batch 2: Frontend State And CI Fail-Closed Routing

### AI operations use current blocks and reject conflicts

The request captures its starting blocks, while the AI editing hook maintains a
latest-blocks ref refreshed on every render. After the existing note ID/request
ID guards accept a response, a pure conflict helper compares the starting and
current versions of every block the operations would replace or remove.

Unrelated intervening edits are preserved by applying operations to the current
array and pushing that same current array onto the undo stack. If a targeted
block changed, the complete response is rejected, no undo entry is created, and
the UI tells the user that the note changed and the action must be generated
again. A `replace_blocks` operation conflicts with any intervening block change;
an insertion conflicts only if its new block ID now exists. Tests cover edits
to targeted and unrelated blocks, whole-document replacement, inserted-ID
collision, and exact undo restoration.

The existing overwrite-confirmation decision remains based on the state when
the user starts the action. This remediation changes response application, not
whether a request is initially allowed.

### Bounded and cancellable task polling

Expose an `ApiError` carrying HTTP status while preserving its message and
`Error` behavior for all existing callers. Allow `importApi.taskStatus` to
accept an `AbortSignal`. Each polling request owns an AbortController and a
10-second timeout. Effect cleanup aborts every controller owned by that effect;
in-flight deduplication must not let an old effect abort a request newly owned
by another effect.

Polling terminal rules are:

- Backend `completed`, `failed`, and `interrupted` remain terminal.
- HTTP 401, 403, and 404 become a local interrupted terminal immediately, with
  a user-visible message and no further request.
- Abort due to the per-request timeout and other transport/5xx failures retry
  after two seconds. Five consecutive failures become a local interrupted
  terminal; any valid response resets the failure count.
- A task still nonterminal two hours after tracking begins becomes locally
  interrupted. The long ceiling accommodates legitimate transcription while
  preventing permanent background work.
- Component unmount aborts requests and schedules no retry. Adding a batch or
  changing callback identity must preserve one request per task through the
  existing in-flight map.

Tests use fake timers and controllable real promises to prove timeout abort,
permanent-error termination, bounded transient retries, total lifetime,
effect cleanup, and continued independence of concurrent batches.

### Explicit document routing

Replace suffix-based docs-only fallback with a small allowlist. Only root
`README.md` may skip both product jobs. Existing plan files continue to require
Backend; repository instructions and micro-task policy continue to require both
jobs.

`docs/security/`, `docs/deployment/`, and all `docs/superpowers/specs/` paths
require Backend and Frontend. Any other unrecognized path, including unknown
Markdown, text, or reStructuredText, requires both jobs. Tests execute the
classifier for a security exception file, an ordinary spec, a deployment
document, an unknown root document, an unknown nested document, and an allowed
README. Protected pushes continue to force both jobs regardless of paths.

## Error Handling And Compatibility

- External reset-send responses do not expose SMTP outcome. Server logs contain
  only enough context to diagnose delivery failure and never include secrets.
- Credential-version mismatches use the existing unauthorized response and do
  not reveal why a session became invalid.
- Legacy SQLite migration is idempotent. It does not drop sessions, users, or
  credentials and does not require a one-off manual command.
- Local polling terminal records exist only in client memory; they do not mutate
  the server's ingestion task status.
- `ApiError` is backward compatible with callers that handle ordinary `Error`.
- Nginx changes affect only the version-controlled example. They must be merged
  into the active ECS configuration during a separately approved deployment;
  this task does not access or reload the server.

## Verification And Delivery

Each behavior starts with a focused failing regression test and reaches green
before the next behavior begins. Batch 1 and Batch 2 receive separate focused
commits and independent reviews. Final acceptance requires:

- Password-reset, authentication, session, SQLite migration, rate-limit, and
  Nginx configuration tests pass, including real independent-session races.
- Video-note AI and import polling tests pass with deterministic delayed
  responses and fake timers.
- CI classifier, workflow, dependency policy, plan lifecycle, and plan index
  tests pass.
- Full `scripts/verify-before-commit.ps1` passes.
- Frontend lint, all Vitest tests, production build, and Playwright pass.
- Fresh npm 10.9.2 dependency installation is clean and production/full audits
  report zero vulnerabilities.
- Independent review reports no Critical or Important finding.
- Normal pre-commit hooks pass; no hook is bypassed.
- The release branch is fast-forwarded and pushed without force. Push and
  pull-request workflows for the exact final SHA both pass `Changes`, `Backend`,
  `Frontend`, and `CI Success`.

Pull request 7 remains Open and Ready. This work does not merge the pull request
into `main`, publish a production release from `main`, copy production secrets,
modify the active ECS host, or deploy containers.

## Out Of Scope

- Replacing the email provider or adding background mail infrastructure.
- Adding device/session management UI.
- Redesigning AI operations or overwrite-confirmation semantics.
- Persisting client-local polling failures back to ingestion tasks.
- Broad dependency upgrades or changing audit thresholds.
- Resolving unrelated packages installed in the developer's global Python
  environment but absent from repository requirements.
- Production deployment or direct Nginx reload.
