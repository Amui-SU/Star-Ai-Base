# CI Security Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce a zero-vulnerability production dependency gate while keeping the unresolved ESLint development-chain advisory visible and bounding CI resource usage.

**Architecture:** Extend the existing frontend CI job with one blocking production audit step and one explicitly non-blocking full audit step. Keep the workflow's existing read-only token permission and add job-level timeouts. Protect these requirements with structural pytest assertions against the parsed workflow.

**Tech Stack:** GitHub Actions YAML, npm audit, pytest, PyYAML

---

### Task 1: Specify the CI security policy

**Files:**

- Modify: `tests/test_ci_workflow.py`

- [ ] **Step 1: Add a failing audit-policy test**

```python
def test_ci_blocks_production_audit_failures_and_reports_full_audit():
    workflow = yaml.safe_load(read_ci_workflow())
    steps = {
        step.get("name"): step
        for step in workflow["jobs"]["frontend"]["steps"]
        if isinstance(step, dict)
    }

    production_audit = steps["Audit production dependencies"]
    assert production_audit["run"] == "npm audit --omit=dev --audit-level=high"
    assert production_audit.get("continue-on-error") is not True

    full_audit = steps["Report full dependency audit"]
    assert full_audit["run"] == "npm audit --audit-level=high"
    assert full_audit["continue-on-error"] is True
```

- [ ] **Step 2: Add a failing timeout-policy test**

```python
def test_ci_jobs_have_bounded_runtime():
    workflow = yaml.safe_load(read_ci_workflow())

    assert workflow["jobs"]["backend"]["timeout-minutes"] == 30
    assert workflow["jobs"]["frontend"]["timeout-minutes"] == 30
```

- [ ] **Step 3: Verify the tests fail for the missing policy**

Run: `python -m pytest tests/test_ci_workflow.py -q`

Expected: FAIL because the audit steps and CI job timeouts do not yet exist.

### Task 2: Implement the CI security policy

**Files:**

- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_ci_workflow.py`

- [ ] **Step 1: Bound both CI jobs**

Add `timeout-minutes: 30` to the `backend` and `frontend` jobs while retaining the workflow-level `permissions: contents: read` policy.

- [ ] **Step 2: Add the blocking production audit**

```yaml
- name: Audit production dependencies
  run: npm audit --omit=dev --audit-level=high
```

Place it immediately after `npm ci` so vulnerable production dependencies stop the frontend job before browser installation and tests.

- [ ] **Step 3: Add the visible non-blocking full audit**

```yaml
- name: Report full dependency audit
  continue-on-error: true
  run: npm audit --audit-level=high
```

Place it after the production gate. Do not suppress output with shell fallbacks such as `|| true`.

- [ ] **Step 4: Verify the structural tests pass**

Run: `python -m pytest tests/test_ci_workflow.py -q`

Expected: all CI workflow tests pass.

### Task 3: Verify and deliver

**Files:**

- Create: `docs/security/dependency-audit-exceptions.md`
- Create: `tests/test_dependency_security_policy.py`
- Verify: `.github/workflows/ci.yml`
- Verify: `tests/test_ci_workflow.py`

- [ ] **Step 1: Add a failing test for a time-bounded exception record**

```python
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_brace_expansion_exception_is_documented_and_time_bounded():
    policy = (
        PROJECT_ROOT / "docs" / "security" / "dependency-audit-exceptions.md"
    ).read_text(encoding="utf-8")

    for required in [
        "GHSA-mh99-v99m-4gvg",
        "development-only",
        "2026-08-11",
        "npm audit --omit=dev --audit-level=high",
    ]:
        assert required in policy
```

Run: `python -m pytest tests/test_dependency_security_policy.py -q`

Expected: FAIL because the exception register does not exist.

- [ ] **Step 2: Document the active exception and removal criteria**

Create `docs/security/dependency-audit-exceptions.md` with the advisory ID, development-only dependency path, CI mitigations, 2026-08-11 review date, and removal conditions.

- [ ] **Step 3: Verify audits locally**

Run: `cd frontend && npm audit --omit=dev --audit-level=high`

Expected: exit 0 and zero production vulnerabilities.

Run: `cd frontend && npm audit --audit-level=high`

Expected: non-zero with only the documented ESLint/minimatch/brace-expansion development-chain advisory.

- [ ] **Step 4: Run repository and frontend regression checks**

Run: `python -m pytest tests/test_ci_workflow.py -q`

Run: `cd frontend && npm run lint && npm test && npm run build && npm run test:e2e`

Expected: all commands pass.

- [ ] **Step 5: Review and commit**

```bash
git diff --check
git add .github/workflows/ci.yml tests/test_ci_workflow.py tests/test_dependency_security_policy.py docs/security/dependency-audit-exceptions.md docs/superpowers/plans/2026-07-28-ci-security-guardrails.md
git commit -m "ci: enforce frontend security audit policy"
```
