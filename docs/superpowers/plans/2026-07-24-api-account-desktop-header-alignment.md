# API Account Desktop Header Alignment Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the desktop API account editor header share one stable vertical center line and consistent control sizing.

**Architecture:** Keep the existing React markup and responsive breakpoint. Add a focused style regression, then scope all visual changes to desktop rules in `api-account-workspace.css` so mobile behavior remains untouched.

**Tech Stack:** React, CSS, Vitest, Playwright

---

### Task 1: Guard the desktop header geometry

**Files:**

- Modify: `frontend/app/api-key-config-layout.test.ts`
- Test: `frontend/app/api-key-config-layout.test.ts`

- [x] **Step 1: Write the failing style regression**

Add a test under `describe("personal API account layout")` that requires a 64px desktop header, 36px action controls, centered actions, tightened title lines, and no primary-button hover translation inside this header:

```ts
it("aligns the desktop workspace header on one stable center line", () => {
  expect(stylesheet).toMatch(
    /\.api-account-workspace-header\s*\{[^}]*min-height:\s*64px;[^}]*align-items:\s*center;/s,
  );
  expect(stylesheet).toMatch(
    /\.api-account-workspace-actions\s*\{[^}]*align-items:\s*center;[^}]*min-height:\s*36px;/s,
  );
  expect(stylesheet).toMatch(
    /\.api-account-workspace-actions\s+\.btn\s*\{[^}]*height:\s*36px;[^}]*padding:\s*0 16px;/s,
  );
  expect(stylesheet).toMatch(
    /\.api-account-workspace-title\s*\{[^}]*display:\s*grid;[^}]*align-content:\s*center;/s,
  );
  expect(stylesheet).toMatch(
    /\.api-account-workspace-actions\s+\.btn-primary:hover\s*\{[^}]*transform:\s*none;/s,
  );
});
```

- [x] **Step 2: Run the test and verify RED**

Run:

```powershell
cd frontend
npx vitest run app/api-key-config-layout.test.ts
```

Expected: the new desktop header geometry test fails because the scoped rules do not exist yet.

### Task 2: Normalize the desktop header styles

**Files:**

- Modify: `frontend/app/styles/api-account-workspace.css`
- Test: `frontend/app/api-key-config-layout.test.ts`

- [x] **Step 1: Implement the desktop-only geometry**

Update the existing desktop rules without changing the `@media (max-width: 720px)` block:

```css
.api-account-workspace-header {
  min-height: 64px;
  align-items: center;
  padding: 8px clamp(16px, 3vw, 36px);
}

.api-account-workspace-title {
  display: grid;
  min-width: 0;
  align-content: center;
  gap: 2px;
}

.api-account-workspace-title h1 {
  line-height: 1.15;
}

.api-account-workspace-title span {
  line-height: 1.1;
}

.api-account-workspace-actions {
  min-height: 36px;
  align-items: center;
  gap: 8px;
}

.api-account-workspace-actions .btn {
  height: 36px;
  padding: 0 16px;
}

.api-account-workspace-actions .btn-primary:hover {
  transform: none;
}
```

- [x] **Step 2: Run focused tests and verify GREEN**

Run:

```powershell
cd frontend
npx vitest run app/api-key-config-layout.test.ts components/api-accounts/ApiAccountWorkspace.test.tsx
npm run lint
```

Expected: all focused tests pass and ESLint exits with code 0.

### Task 3: Verify the rendered desktop editor

**Files:**

- No repository files
- Screenshot: outside the repository in the current visualization directory

- [x] **Step 1: Run the desktop Playwright flow**

Open the API account list, edit an account at `1440x900`, and capture the first editor viewport. Verify the header button, provider mark, title block, action buttons, and close button share a stable visual center with no overlap or horizontal overflow.

- [x] **Step 2: Check runtime health**

Confirm the page title and editor dialog identity, meaningful rendered content, no Next.js error overlay, and no relevant console errors or warnings.

- [x] **Step 3: Commit the implementation**

```powershell
git add frontend/app/api-key-config-layout.test.ts frontend/app/styles/api-account-workspace.css
git commit -m "style: align API account desktop header"
```
