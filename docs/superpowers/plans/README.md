# Implementation Plan Lifecycle

This directory contains historical and active implementation plans. The
standard `**Status:**` field near each plan title is authoritative; command and
code snippets remain historical execution guidance and may be superseded by
current repository policy.

The plan index is generated from those status fields. Do not edit its rows by
hand.

## Status Values

- `completed`: the planned behavior is integrated and its checklist is closed.
- `partial`: some behavior is integrated and the plan names an active remainder.
- `superseded`: a newer plan or policy replaces this plan.
- `planned`: implementation has not started.

## Updating The Index

Update the generated region after adding a plan or changing a status:

```powershell
python scripts/generate-plan-index.py
```

Check for drift without changing the file:

```powershell
python scripts/generate-plan-index.py --check
```

## Plan Index

<!-- BEGIN GENERATED PLAN INDEX -->

| Plan                                                                                                             | Status     |
| ---------------------------------------------------------------------------------------------------------------- | ---------- |
| [2026-06-26-chat-history.md](2026-06-26-chat-history.md)                                                         | completed  |
| [2026-06-27-four-issues-closeout.md](2026-06-27-four-issues-closeout.md)                                         | completed  |
| [2026-06-27-medium-low-risk-refactor.md](2026-06-27-medium-low-risk-refactor.md)                                 | completed  |
| [2026-06-27-pre-release-architecture-maintenance.md](2026-06-27-pre-release-architecture-maintenance.md)         | completed  |
| [2026-06-27-pre-release-architecture-round2.md](2026-06-27-pre-release-architecture-round2.md)                   | completed  |
| [2026-06-27-pre-release-architecture-round3.md](2026-06-27-pre-release-architecture-round3.md)                   | completed  |
| [2026-06-27-pre-release-hardening.md](2026-06-27-pre-release-hardening.md)                                       | completed  |
| [2026-07-02-video-notes-mvp.md](2026-07-02-video-notes-mvp.md)                                                   | completed  |
| [2026-07-17-container-image-deployment.md](2026-07-17-container-image-deployment.md)                             | completed  |
| [2026-07-20-acr-personal-compatibility.md](2026-07-20-acr-personal-compatibility.md)                             | completed  |
| [2026-07-22-history-new-chat-live-resize.md](2026-07-22-history-new-chat-live-resize.md)                         | completed  |
| [2026-07-22-verifiable-container-release.md](2026-07-22-verifiable-container-release.md)                         | completed  |
| [2026-07-23-api-key-config-ux.md](2026-07-23-api-key-config-ux.md)                                               | completed  |
| [2026-07-24-api-account-desktop-header-alignment.md](2026-07-24-api-account-desktop-header-alignment.md)         | completed  |
| [2026-07-24-api-account-fullscreen-workspace.md](2026-07-24-api-account-fullscreen-workspace.md)                 | completed  |
| [2026-07-27-video-note-ui-polish.md](2026-07-27-video-note-ui-polish.md)                                         | completed  |
| [2026-07-28-auth-page-desktop-alignment.md](2026-07-28-auth-page-desktop-alignment.md)                           | completed  |
| [2026-07-28-ci-security-guardrails.md](2026-07-28-ci-security-guardrails.md)                                     | completed  |
| [2026-07-28-micro-task-fast-lane.md](2026-07-28-micro-task-fast-lane.md)                                         | superseded |
| [2026-07-28-playwright-auth-validation.md](2026-07-28-playwright-auth-validation.md)                             | completed  |
| [2026-07-28-python-runtime-selection.md](2026-07-28-python-runtime-selection.md)                                 | completed  |
| [2026-07-28-video-note-id-reconciliation-performance.md](2026-07-28-video-note-id-reconciliation-performance.md) | completed  |
| [2026-07-29-forgot-password.md](2026-07-29-forgot-password.md)                                                   | completed  |
| [2026-07-29-micro-task-fast-lane-v2.md](2026-07-29-micro-task-fast-lane-v2.md)                                   | completed  |
| [2026-07-29-video-note-branch-integration.md](2026-07-29-video-note-branch-integration.md)                       | completed  |
| [2026-07-30-deterministic-pre-commit-hooks.md](2026-07-30-deterministic-pre-commit-hooks.md)                     | completed  |
| [2026-07-30-path-aware-ci.md](2026-07-30-path-aware-ci.md)                                                       | completed  |
| [2026-07-30-worktree-dependency-reuse.md](2026-07-30-worktree-dependency-reuse.md)                               | completed  |
| [2026-08-06-dependency-and-plan-lifecycle.md](2026-08-06-dependency-and-plan-lifecycle.md)                       | completed  |
| [2026-08-07-generated-plan-index.md](2026-08-07-generated-plan-index.md)                                         | completed  |
| [2026-08-22-ci-release-blockers.md](2026-08-22-ci-release-blockers.md)                                           | completed  |
| [2026-08-25-pr7-review-remediation.md](2026-08-25-pr7-review-remediation.md)                                     | completed  |
| [2026-09-01-yaml-advisory-remediation.md](2026-09-01-yaml-advisory-remediation.md)                               | completed  |
| [2026-09-08-pr7-adversarial-remediation.md](2026-09-08-pr7-adversarial-remediation.md)                           | planned    |

<!-- END GENERATED PLAN INDEX -->
