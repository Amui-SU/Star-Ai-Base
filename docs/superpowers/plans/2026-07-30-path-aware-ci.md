# Path-aware CI Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skip unrelated heavy pull-request jobs while preserving complete CI for pushes to main and release branches.

**Architecture:** A repository-owned Python classifier converts changed paths into backend/frontend/docs-only outputs. GitHub Actions uses those outputs for pull requests, forces both heavy jobs on protected pushes, caches pip dependencies, and exposes one always-running summary check.

**Tech Stack:** Python 3.12, pytest, GitHub Actions YAML, Bash, setup-python pip cache.

---

## File map

- Create `scripts/classify-ci-paths.py`: pure path policy plus NUL-input CLI.
- Create `tests/developer_workflow/test_ci_paths.py`: table-driven policy and CLI contracts.
- Modify `.github/workflows/ci.yml`: changes job, conditions, cache, release pushes, and summary.
- Modify `frontend/package.json` and `frontend/package-lock.json`: pin the YAML parser used by local workflow validation.
- Modify `AGENTS.md`: document PR path routing and protected-push full verification.

### Task 1: Path classifier

**Files:**

- Create: `scripts/classify-ci-paths.py`
- Create: `tests/developer_workflow/test_ci_paths.py`

- [x] **Step 1: Write failing policy tests**

```python
@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["docs/user-guide.md"], {"backend": False, "frontend": False, "docs_only": True}),
        (["app/main.py"], {"backend": True, "frontend": False, "docs_only": False}),
        (["tests/test_auth.py"], {"backend": True, "frontend": False, "docs_only": False}),
        (["frontend/components/App.tsx"], {"backend": False, "frontend": True, "docs_only": False}),
        (["frontend/package-lock.json"], {"backend": False, "frontend": True, "docs_only": False}),
        (["AGENTS.md"], {"backend": True, "frontend": True, "docs_only": False}),
        (["scripts/verify-fast.ps1"], {"backend": True, "frontend": True, "docs_only": False}),
        ([".github/workflows/ci.yml"], {"backend": True, "frontend": True, "docs_only": False}),
        (["unknown.binary"], {"backend": True, "frontend": True, "docs_only": False}),
        (
            ["app/main.py", "frontend/lib/api.ts"],
            {"backend": True, "frontend": True, "docs_only": False},
        ),
    ],
)
def test_classify_paths(paths, expected):
    assert classify_paths(paths) == expected


def test_force_full_ignores_paths():
    assert classify_paths(["docs/readme.md"], force_full=True) == {
        "backend": True, "frontend": True, "docs_only": False,
    }
```

- [x] **Step 2: Write failing NUL CLI tests**

```python
def test_cli_reads_nul_names_and_writes_github_outputs(tmp_path):
    output = tmp_path / "github-output"
    result = subprocess.run(
        [
            sys.executable, "scripts/classify-ci-paths.py",
            "--stdin-zero", "--github-output", str(output),
        ],
        input=b"docs/space name.md\0frontend/lib/\xe4\xb8\xad.ts\0",
        cwd=PROJECT_ROOT,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert output.read_text(encoding="utf-8").splitlines() == [
        "backend=false", "frontend=true", "docs_only=false",
    ]


def run_classifier(payload: bytes, output: Path):
    return subprocess.run(
        [
            sys.executable, "scripts/classify-ci-paths.py",
            "--stdin-zero", "--github-output", str(output),
        ],
        input=payload,
        cwd=PROJECT_ROOT,
        capture_output=True,
    )


def test_invalid_utf8_fails_closed(tmp_path):
    output = tmp_path / "github-output"
    result = run_classifier(b"docs/ok.md\0\xff\0", output)
    assert result.returncode != 0
    assert not output.exists()
```

- [x] **Step 3: Verify RED**

Run: `python -m pytest -q tests/developer_workflow/test_ci_paths.py`

Expected: FAIL because the classifier is absent.

- [x] **Step 4: Implement the pure classifier**

```python
DOC_SUFFIXES = {".md", ".txt", ".rst"}
SHARED_EXACT = {
    ".github/workflows/ci.yml",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/micro-task-template.md",
    "pytest.ini",
    "requirements.txt",
    "scripts/classify-ci-paths.py",
    "scripts/verify-fast.ps1",
    "scripts/verify-before-commit.ps1",
    "scripts/verify-staged.ps1",
}
POLICY_PREFIXES = (
    "docs/superpowers/specs/2026-07-29-micro-task-fast-lane",
    "docs/superpowers/plans/2026-07-29-micro-task-fast-lane",
)
BACKEND_PREFIXES = ("app/", "tests/")
FRONTEND_PREFIXES = ("frontend/",)


def classify_paths(paths: list[str], force_full: bool = False) -> dict[str, bool]:
    if force_full:
        return {"backend": True, "frontend": True, "docs_only": False}
    backend = False
    frontend = False
    docs_only = bool(paths)
    for raw_path in paths:
        path = raw_path.replace("\\", "/")
        if (
            path in SHARED_EXACT
            or path.startswith(".github/")
            or path.startswith(POLICY_PREFIXES)
        ):
            backend = frontend = True
            docs_only = False
        elif path.startswith(BACKEND_PREFIXES) or (
            path.startswith("scripts/") and path.endswith((".py", ".ps1", ".sh"))
        ):
            backend = True
            docs_only = False
        elif path.startswith(FRONTEND_PREFIXES):
            frontend = True
            docs_only = False
        elif Path(path).suffix.lower() not in DOC_SUFFIXES:
            backend = frontend = True
            docs_only = False
    if not paths:
        backend = frontend = True
        docs_only = False
    return {"backend": backend, "frontend": frontend, "docs_only": docs_only}
```

Treat fast-lane specification and plan paths as shared exact/prefix policy paths
because backend contract tests assert their contents. Unknown paths force both
jobs instead of being skipped.

- [x] **Step 5: Implement strict CLI output**

```python
def read_zero_paths(stream: BinaryIO) -> list[str]:
    payload = stream.read()
    chunks = payload.split(b"\0")
    if chunks[-1] != b"":
        raise ValueError("NUL-delimited input must end with NUL")
    return [chunk.decode("utf-8", errors="strict") for chunk in chunks[:-1]]


def write_outputs(path: Path, values: dict[str, bool]) -> None:
    lines = [f"{name}={'true' if value else 'false'}" for name, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdin-zero", action="store_true", required=True)
    parser.add_argument("--force-full", action="store_true")
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    values = classify_paths(read_zero_paths(sys.stdin.buffer), args.force_full)
    write_outputs(args.github_output, values)
    return 0
```

Catch only expected decode/value errors at the executable boundary, print a
concise error to stderr, and return non-zero without writing partial outputs.

- [x] **Step 6: Verify GREEN and commit**

Run: `python -m pytest -q tests/developer_workflow/test_ci_paths.py`

Expected: PASS.

```powershell
git add -- scripts/classify-ci-paths.py tests/developer_workflow/test_ci_paths.py
git commit -m "feat: classify ci paths fail closed"
```

### Task 2: Route GitHub Actions jobs

**Files:**

- Modify: `.github/workflows/ci.yml`
- Modify: `tests/developer_workflow/test_ci_paths.py`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

- [x] **Step 1: Add failing workflow structure tests**

```python
def test_ci_has_changes_and_summary_jobs():
    workflow_text = CI_PATH.read_text(encoding="utf-8")
    assert "\n  changes:\n" in workflow_text
    assert "\n  backend:\n" in workflow_text
    assert "\n  frontend:\n" in workflow_text
    assert "\n  ci-success:\n" in workflow_text
    assert workflow_text.count("needs: changes") == 2
    assert "needs: [changes, backend, frontend]" in workflow_text


def test_protected_pushes_force_full_ci():
    workflow_text = CI_PATH.read_text(encoding="utf-8")
    assert "release/**" in workflow_text
    assert "--force-full" in workflow_text
    assert "needs.changes.outputs.backend == 'true'" in workflow_text
    assert "needs.changes.outputs.frontend == 'true'" in workflow_text


def test_backend_uses_official_pip_cache():
    workflow_text = CI_PATH.read_text(encoding="utf-8")
    assert "cache: pip" in workflow_text
    assert "cache-dependency-path: requirements.txt" in workflow_text
```

Use a YAML loader that preserves GitHub's `on` key as a string, or supplement
structural loading with explicit text assertions.

- [x] **Step 2: Verify RED**

Run: `python -m pytest -q tests/developer_workflow/test_ci_paths.py`

Expected: FAIL because the workflow has no routing jobs.

- [x] **Step 3: Pin the workflow YAML parser**

Run from `frontend`:

```powershell
npm install --save-dev --save-exact yaml@2.8.1
node -e "console.log(require('yaml').parse('ok: true').ok)"
```

Expected: `true`; both manifest files record `yaml` version `2.8.1`.

- [x] **Step 4: Add the changes job**

Set triggers to pull requests plus pushes to `main` and `release/**`. Checkout
with `fetch-depth: 0`. The classifier step must have `id: classify` and expose
all three outputs:

```yaml
changes:
  runs-on: ubuntu-latest
  outputs:
    backend: ${{ steps.classify.outputs.backend }}
    frontend: ${{ steps.classify.outputs.frontend }}
    docs_only: ${{ steps.classify.outputs.docs_only }}
  steps:
    - uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0
      with:
        fetch-depth: 0
    - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
      with:
        python-version: "3.12"
    - id: classify
      shell: bash
      env:
        EVENT_NAME: ${{ github.event_name }}
        BASE_SHA: ${{ github.event.pull_request.base.sha }}
        HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}
      run: |
        if [[ "$EVENT_NAME" == "push" ]]; then
          printf '\0' | python scripts/classify-ci-paths.py --stdin-zero --force-full --github-output "$GITHUB_OUTPUT"
        else
          git diff --name-only -z "$BASE_SHA" "$HEAD_SHA" |
            python scripts/classify-ci-paths.py --stdin-zero --github-output "$GITHUB_OUTPUT"
        fi
```

- [x] **Step 5: Gate heavy jobs and enable pip cache**

Add `needs: changes` and the exact Boolean-output conditions to backend and
frontend. Add to setup-python:

```yaml
cache: pip
cache-dependency-path: requirements.txt
```

Do not weaken the frontend steps: audit, Playwright installation, lint, unit
tests, build, and E2E remain present.

- [x] **Step 6: Add an always-running summary**

```yaml
ci-success:
  name: CI Success
  runs-on: ubuntu-latest
  if: always()
  needs: [changes, backend, frontend]
  steps:
    - name: Require expected jobs
      shell: bash
      env:
        CHANGES_RESULT: ${{ needs.changes.result }}
        BACKEND_EXPECTED: ${{ needs.changes.outputs.backend }}
        BACKEND_RESULT: ${{ needs.backend.result }}
        FRONTEND_EXPECTED: ${{ needs.changes.outputs.frontend }}
        FRONTEND_RESULT: ${{ needs.frontend.result }}
      run: |
        [[ "$CHANGES_RESULT" == "success" ]] || exit 1
        [[ "$BACKEND_EXPECTED" != "true" || "$BACKEND_RESULT" == "success" ]] || exit 1
        [[ "$FRONTEND_EXPECTED" != "true" || "$FRONTEND_RESULT" == "success" ]] || exit 1
```

- [x] **Step 7: Verify workflow tests and commit**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_ci_paths.py
git diff --check
```

Expected: PASS.

```powershell
git add -- .github/workflows/ci.yml tests/developer_workflow/test_ci_paths.py frontend/package.json frontend/package-lock.json
git commit -m "ci: skip unrelated pull request jobs"
```

### Task 3: Policy and final CI validation

**Files:**

- Modify: `AGENTS.md`

- [x] **Step 1: Document the boundary**

Add text stating that pull requests use job-level path routing only, unknown and
policy paths fail closed to both jobs, and pushes to `main` and `release/**`
always run full CI.

- [x] **Step 2: Add a policy assertion**

```python
def test_policy_preserves_full_protected_push_ci():
    policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "main" in policy
    assert "release/**" in policy
    assert "unknown paths" in policy
    assert "both backend and frontend" in policy
```

- [x] **Step 3: Run focused and YAML validation**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_ci_paths.py tests/fast_workflow/test_policy.py
node -e "const fs=require('fs'); require('./frontend/node_modules/yaml').parse(fs.readFileSync('.github/workflows/ci.yml','utf8'))"
git diff --check
```

Expected: PASS; the Node command exits 0 after parsing the complete workflow.

- [x] **Step 4: Commit policy**

```powershell
git add -- AGENTS.md tests/developer_workflow/test_ci_paths.py
git commit -m "docs: define path-aware ci boundaries"
```
