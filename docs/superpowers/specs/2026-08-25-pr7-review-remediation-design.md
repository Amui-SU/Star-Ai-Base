# PR 7 Review Remediation Design

## Goal

Remove the merge blockers found in the final review of pull request 7 without
expanding the release scope or weakening the repository's security and CI
policies.

## Scope And Batches

Implementation is split into two release-safe batches:

1. Password-reset security and delivery correctness.
2. CI path routing, import completion refresh, and pull-request metadata.

No unrelated authentication redesign, CI job split, dependency upgrade, or
import workflow redesign belongs in this remediation.

## Password-Reset Security

The send endpoint must return the same successful status and generic body for
an unknown address, an inactive account, and an active account that already
has a live reset code. Debug mode may continue returning a generated code for
local testing, but callers must not infer account state from status or message.

`password_reset_codes.email` becomes unique. Existing SQLite databases retain
the newest row per email before a unique index is created. New databases also
declare the uniqueness rule in SQLAlchemy metadata. A competing send that
loses the insert race returns the generic response and does not send a second
email.

Incorrect confirmation attempts use a conditional database update that
increments `attempts` atomically. The attempt that reaches the configured
limit removes the code. A correct confirmation atomically deletes and returns
the matching live code before changing the password, so one code can succeed
only once even under parallel requests. Password and session changes remain
in the same transaction as successful consumption.

The reset-code row is reserved before delivery to preserve the uniqueness
guarantee. If SMTP delivery fails, the exact reserved row is deleted and the
cleanup is committed, allowing an immediate retry. Reset messages use a
password-reset-specific subject and body rather than registration copy.

## CI Path Routing

`requirements-dev.txt` is a backend dependency input and must run backend CI.
Plan lifecycle inputs under `docs/superpowers/plans/`, the generated plan
index, and the plan lifecycle contract must not be treated as inert docs.
They route to backend CI so the existing lifecycle/index tests execute. This
change deliberately reuses the current job graph; introducing a separate
lightweight policy job is deferred to the workflow-latency follow-up.

Classifier tests cover the exact dependency file and representative plan and
index paths. Unknown paths remain fail-closed to full CI.

## Import Completion Refresh

Submitting an import only means work was queued, so it must not be the final
content-ready signal. The import hook tracks each submitted task batch and
calls `onImported` once when that batch reaches terminal state with at least
one completed task. `failed` and `interrupted` are terminal; neither may poll
forever. A later batch receives its own single notification.

The existing `kb-stats` refresh version remains the page-level content-change
signal. `useChatKnowledgeContext` reloads both knowledge-base statistics and
scope options when that version changes, while resetting the conversation
only when the knowledge-base ID changes. Completing an import therefore makes
new videos selectable without clearing the current chat.

## Verification And Release Gate

Each behavior change follows red-green TDD with focused backend, classifier,
and frontend tests. The completed branch then runs the repository's full
verification, production and full high-severity audits, and a second code
review. After fast-forward integration into the release branch, pull request 7
is updated with current commit/test/audit facts and pushed. It becomes Ready
only after fresh push and pull-request CI runs both pass and the final review
contains no Critical or Important findings.

## Out Of Scope

- Splitting the existing Backend job into a separate policy job.
- Eliminating duplicate push and pull-request workflow runs.
- Fixing moderate dependency advisories that do not cross the high-severity
  release threshold.
- Merging pull request 7 into `main` or deploying production.
