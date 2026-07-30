# Deterministic Pre-commit Hooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-file, network-capable global commit checks with an opt-in repository checker and a deterministic batched fallback.

**Architecture:** A Bash global-hook template reads NUL-delimited staged names and dispatches only when `workflow.useRepositoryHook=true`; otherwise it uses installed tools without downloading anything. A PowerShell repository checker uses pinned local Prettier and Black, while a tested installer backs up and atomically replaces the live global hook.

**Tech Stack:** Bash, PowerShell 5.1, Python 3.12/pytest, Git, npm, Prettier 3.

---

## File map

- Create `scripts/git-hooks/pre-commit`: global dispatcher and generic fallback.
- Create `scripts/verify-staged.ps1`: repository staged checker.
- Create `scripts/install-global-hook.ps1`: backup and installation entry point.
- Create `tests/developer_workflow/__init__.py` and `support.py`: isolated Git/process helpers.
- Create `tests/developer_workflow/test_global_hook.py`, `test_verify_staged.py`, and `test_hook_installer.py`.
- Modify `frontend/package.json`, `frontend/package-lock.json`, and `AGENTS.md`.

### Task 1: Isolated workflow test support

**Files:**

- Create: `tests/developer_workflow/__init__.py`
- Create: `tests/developer_workflow/support.py`

- [ ] **Step 1: Add bounded subprocess execution**

```python
def run_command(args, cwd, env, timeout=30):
    options = dict(
        cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    process = subprocess.Popen(args, **options)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False, capture_output=True, timeout=10,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.kill()
        raise AssertionError(
            f"timeout: args={args!r} stdout={error.stdout!r} stderr={error.stderr!r}"
        ) from None
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
```

- [ ] **Step 2: Add isolated Git setup**

```python
def init_repo(path):
    path.mkdir()
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = str(path / "empty.gitconfig")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    (path / "empty.gitconfig").write_text("", encoding="utf-8")
    run_command(["git", "init"], path, env)
    run_command(["git", "config", "user.name", "Contract Test"], path, env)
    run_command(["git", "config", "user.email", "test@example.invalid"], path, env)
    return env
```

- [ ] **Step 3: Verify and commit the helpers**

Run: `python -m pytest -q tests/developer_workflow/support.py`

Expected: exit 0 with no import or collection errors.

```powershell
git add -- tests/developer_workflow/__init__.py tests/developer_workflow/support.py
git commit -m "test: add developer workflow contract support"
```

### Task 2: Pinned repository staged checker

**Files:**

- Create: `scripts/verify-staged.ps1`
- Create: `tests/developer_workflow/test_verify_staged.py`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

- [ ] **Step 1: Write failing literal-path and batching tests**

```python
@pytest.mark.parametrize("name", ["space name.md", "中文.md", "line\nbreak.md"])
def test_checker_preserves_literal_staged_names(staged_repo, name):
    repo, env, calls = staged_repo
    stage(repo, env, {name: "# valid\n"})
    result = run_checker(repo, env)
    assert result.returncode == 0, result.stderr
    assert calls("prettier") == [["--check", f"../{name}"]]


def test_checker_batches_each_tool_once(staged_repo):
    repo, env, calls = staged_repo
    stage(repo, env, {
        "a.py": "x = 1\n", "b.py": "y = 2\n",
        "a.md": "# a\n", "frontend/b.ts": "export {}\n",
    })
    result = run_checker(repo, env)
    assert result.returncode == 0, result.stderr
    assert calls("black") == [["--check", "--", "a.py", "b.py"]]
    assert calls("prettier") == [["--check", "../a.md", "b.ts"]]


def test_checker_fails_when_pinned_prettier_is_missing(staged_repo):
    repo, env, _ = staged_repo
    stage(repo, env, {"note.md": "# note\n"})
    remove_local_prettier(repo)
    result = run_checker(repo, env)
    assert result.returncode != 0
    assert "prepare frontend dependencies" in result.stderr.lower()
```

Also add cases for absolute paths, `..`, filesystem links, Git mode `120000`,
missing staged files, formatter failure propagation, and
`git diff --cached --check` failure. Recording tool shims must preserve every
argument and checker subprocesses must have a 60-second timeout.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q tests/developer_workflow/test_verify_staged.py`

Expected: FAIL because `scripts/verify-staged.ps1` is absent.

- [ ] **Step 3: Pin Prettier**

Run from `frontend`:

```powershell
npm install --save-dev --save-exact prettier@3.6.2
npm exec --no -- prettier --version
```

Expected: `3.6.2`; both manifest files contain the exact version.

- [ ] **Step 4: Implement `scripts/verify-staged.ps1`**

Reuse the native NUL reader and safe path/link checks from
`scripts/verify-fast.ps1`. The main flow is:

```powershell
$staged = @(Get-GitNullSeparatedPaths @(
    "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"
))
git diff --cached --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$pythonFiles = @(Select-SafeStagedFiles $staged @(".py"))
$webFiles = @(Select-SafeStagedFiles $staged @(
    ".js", ".ts", ".jsx", ".tsx", ".json", ".css", ".scss", ".less",
    ".html", ".md", ".yaml", ".yml"
))
if ($pythonFiles.Count) {
    python -m black --check -- @pythonFiles
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if ($webFiles.Count) {
    $prettier = Resolve-PinnedPrettier
    Push-Location $frontendRoot
    try { & $prettier --check @(Convert-ToFrontendPaths $webFiles) }
    finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

`Select-SafeStagedFiles` fails closed for repository escape, reparse points,
Git mode `120000`, and missing paths. `Resolve-PinnedPrettier` selects only
`frontend/node_modules/.bin/prettier(.cmd)` and prints the dependency
preparation command when absent.

- [ ] **Step 5: Verify GREEN and commit**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_verify_staged.py tests/fast_workflow/test_target_security.py
```

Expected: PASS.

```powershell
git add -- scripts/verify-staged.ps1 tests/developer_workflow/test_verify_staged.py frontend/package.json frontend/package-lock.json
git commit -m "feat: add deterministic staged verification"
```

### Task 3: Global dispatcher and no-network fallback

**Files:**

- Create: `scripts/git-hooks/pre-commit`
- Create: `tests/developer_workflow/test_global_hook.py`

- [ ] **Step 1: Write failing dispatcher contracts**

```python
def test_true_opt_in_dispatches_fixed_script(global_repo):
    repo, env, calls = global_repo
    git(repo, env, "config", "workflow.useRepositoryHook", "true")
    stage(repo, env, {"note.md": "# note\n"})
    result = run_hook(repo, env)
    assert result.returncode == 0, result.stderr
    assert calls("powershell") == [[
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        "scripts/verify-staged.ps1",
    ]]


def test_non_boolean_config_is_not_evaluated(global_repo):
    repo, env, calls = global_repo
    git(repo, env, "config", "workflow.useRepositoryHook", "touch owned")
    result = run_hook(repo, env)
    assert result.returncode == 0
    assert not (repo / "owned").exists()
    assert calls("powershell") == []


def test_fallback_batches_without_npx(global_repo):
    repo, env, calls = global_repo
    stage(repo, env, {"one.md": "# one\n", "two.md": "# two\n"})
    result = run_hook(repo, env)
    assert result.returncode == 0, result.stderr
    assert calls("npx") == []
    assert calls("prettier") == [["--check", "--", "one.md", "two.md"]]
```

Add empty-index, Unicode/newline filename, missing-tool warning, batched
Ruff/Black, and non-zero formatter cases.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q tests/developer_workflow/test_global_hook.py`

Expected: FAIL because `scripts/git-hooks/pre-commit` is absent.

- [ ] **Step 3: Implement the Bash template**

```bash
#!/usr/bin/env bash
set -uo pipefail
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$root" || exit 1

if [[ "$(git config --bool --get workflow.useRepositoryHook 2>/dev/null)" == true ]]; then
  [[ -f scripts/verify-staged.ps1 ]] || {
    echo "[pre-commit] missing scripts/verify-staged.ps1" >&2; exit 1;
  }
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/verify-staged.ps1
  exit $?
fi

mapfile -d '' staged < <(git diff --cached --name-only -z --diff-filter=ACMR)
python_files=()
web_files=()
for path in "${staged[@]}"; do
  case "$path" in
    *.py) python_files+=("$path") ;;
    *.js|*.ts|*.jsx|*.tsx|*.json|*.css|*.scss|*.less|*.html|*.md|*.yaml|*.yml)
      web_files+=("$path") ;;
  esac
done
status=0
if ((${#python_files[@]})); then
  if command -v ruff >/dev/null 2>&1; then
    ruff check --no-fix -- "${python_files[@]}" || status=1
  elif command -v black >/dev/null 2>&1; then
    black --check --quiet -- "${python_files[@]}" || status=1
  else
    python -m py_compile "${python_files[@]}" || status=1
  fi
fi
if ((${#web_files[@]})); then
  if command -v prettier >/dev/null 2>&1; then
    prettier --check -- "${web_files[@]}" || status=1
  else
    echo "[pre-commit] warning: installed Prettier not found; skipped web formatting" >&2
  fi
fi
exit "$status"
```

The final file must contain no `eval`, `npx`, `npm exec`, `--yes`, `curl`, or
package-install command. Contract tests assert the resulting argv rather than
matching only source text.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest -q tests/developer_workflow/test_global_hook.py`

Expected: PASS.

```powershell
git add -- scripts/git-hooks/pre-commit tests/developer_workflow/test_global_hook.py
git commit -m "feat: add no-network global hook dispatcher"
```

### Task 4: Safe installer and live rollout

**Files:**

- Create: `scripts/install-global-hook.ps1`
- Create: `tests/developer_workflow/test_hook_installer.py`
- Modify: `AGENTS.md`
- Modify after tests: `C:/Users/amui/.git-hooks/pre-commit`

- [ ] **Step 1: Write failing installer contracts**

```python
def test_installer_backs_up_and_opts_in(installer_repo):
    repo, env, hook_dir = installer_repo
    (hook_dir / "pre-commit").write_text("old\n", encoding="utf-8")
    result = run_installer(repo, env, hook_dir)
    assert result.returncode == 0, result.stderr
    backups = list(hook_dir.glob("pre-commit.backup-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "old\n"
    assert (hook_dir / "pre-commit").read_bytes() == (
        repo / "scripts/git-hooks/pre-commit"
    ).read_bytes()
    assert git_config(repo, env, "workflow.useRepositoryHook") == "true"
    assert "restore" in result.stdout.lower()


def test_installer_rejects_reparse_hook_directory(installer_repo):
    repo, env, hook_dir = installer_repo
    real_directory = hook_dir.parent / "real-hooks"
    real_directory.mkdir()
    hook_dir.rmdir()
    os.symlink(real_directory, hook_dir, target_is_directory=True)
    result = run_installer(repo, env, hook_dir)
    assert result.returncode != 0
    assert "reparse" in result.stderr.lower()
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q tests/developer_workflow/test_hook_installer.py`

Expected: FAIL because the installer is absent.

- [ ] **Step 3: Implement atomic backup and replacement**

```powershell
param([string]$HookDirectory = "")
$ErrorActionPreference = "Stop"
$root = (git rev-parse --show-toplevel).Trim()
if (-not $HookDirectory) { $HookDirectory = git config --global --get core.hooksPath }
if (-not $HookDirectory) { throw "Global core.hooksPath is not configured." }
$directory = [IO.Path]::GetFullPath($HookDirectory)
$parent = Split-Path -Parent $directory
if (-not (Test-Path -LiteralPath $directory)) {
    $parentItem = Get-Item -LiteralPath $parent -ErrorAction Stop
    if ($parentItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Hook directory parent must not be a reparse point: $parent"
    }
    [IO.Directory]::CreateDirectory($directory) | Out-Null
}
if ((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw "Hook directory must not be a reparse point: $directory"
}
$source = Join-Path $root "scripts/git-hooks/pre-commit"
$destination = Join-Path $directory "pre-commit"
$backup = "$destination.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss').bak"
if (Test-Path -LiteralPath $destination -PathType Leaf) {
    Copy-Item -LiteralPath $destination -Destination $backup -ErrorAction Stop
}
$temporary = "$destination.installing-$PID"
Copy-Item -LiteralPath $source -Destination $temporary -ErrorAction Stop
Move-Item -LiteralPath $temporary -Destination $destination -Force
git config --local workflow.useRepositoryHook true
if ($LASTEXITCODE -ne 0) { throw "Failed to set repository opt-in." }
Write-Host "Installed: $destination"
Write-Host "Restore: Copy-Item -LiteralPath '$backup' -Destination '$destination' -Force"
```

Create a missing hook directory only when its parent exists and is not a
reparse point. Verify temporary and destination paths remain direct children of
the resolved directory.

- [ ] **Step 4: Update policy and verify repository contracts**

Document the installer command, backup/restore behavior, staged-only scope, and
no-download rule in `AGENTS.md`.

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_global_hook.py tests/developer_workflow/test_verify_staged.py tests/developer_workflow/test_hook_installer.py
```

Expected: PASS.

- [ ] **Step 5: Commit repository changes**

```powershell
git add -- scripts/install-global-hook.ps1 tests/developer_workflow/test_hook_installer.py AGENTS.md
git commit -m "feat: install repository-aware commit hooks safely"
```

- [ ] **Step 6: Install and verify the live hook**

Run only after the repository tests pass:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-global-hook.ps1
rg -n "npx|npm exec|--yes|eval|curl" C:\Users\amui\.git-hooks\pre-commit
git config --local --get workflow.useRepositoryHook
```

Expected: installer prints backup/restore paths; `rg` has no matches; Git
config prints `true`. Invoke the live hook against a formatting-clean staged
fixture without committing, verify exit 0 in under five seconds, then restore
the fixture with `apply_patch`.

- [ ] **Step 7: Final verification**

Run:

```powershell
python -m pytest -q tests/developer_workflow tests/fast_workflow
git diff --check
git status --short
```

Expected: PASS and a clean worktree.
