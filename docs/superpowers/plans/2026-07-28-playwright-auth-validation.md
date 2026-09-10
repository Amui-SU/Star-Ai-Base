# Playwright Auth Validation Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal Chromium-based Playwright workflow that automatically verifies the login page at the approved desktop and mobile viewports.

**Architecture:** Playwright lives in the frontend package and starts the existing Next.js development server through `webServer`. One focused E2E file checks page identity, console health, desktop geometry, mobile overflow, and a real form interaction. CI installs only Chromium and runs the E2E script after the existing frontend build.

**Tech Stack:** Next.js, TypeScript, Playwright Test, Chromium, GitHub Actions

---

### Task 1: Define the rendered acceptance test

**Files:**

- Create: `frontend/e2e/auth-responsive.e2e.ts`

- [x] Add desktop `2048x1152` and mobile `390x844` tests for visible content, layout geometry, horizontal overflow, console errors, and email input interaction.
- [x] Run the focused E2E command and confirm it fails because the Playwright script and dependency do not exist.

### Task 2: Add the minimal Playwright runtime

**Files:**

- Create: `frontend/playwright.config.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/.gitignore`

- [x] Install `@playwright/test` as a development dependency.
- [x] Add `test:e2e` and `test:e2e:ui` scripts.
- [x] Configure one Chromium project, `http://127.0.0.1:3100`, automatic Next.js startup, CI retries, and failure-only screenshots/traces.
- [x] Ignore Playwright reports and test results.
- [x] Install Chromium locally and run the focused E2E test.

### Task 3: Add the CI gate

**Files:**

- Modify: `.github/workflows/ci.yml`

- [x] Install Chromium and Linux browser dependencies after `npm ci`.
- [x] Run `npm run test:e2e` after the existing frontend build.

### Task 4: Verify and integrate

- [x] Run frontend unit tests, lint, production build, and Playwright E2E.
- [x] Run backend tests through the repository verification script.
- [x] Review screenshots, console output, final diff, and dependency changes.
- [x] Commit and integrate into `main` without touching unrelated working-tree changes.
