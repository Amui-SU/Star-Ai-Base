# Worktree Dependency Reuse Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare frontend dependencies in temporary worktrees within seconds when the main installation is provably compatible, with a safe isolated-install fallback.

**Architecture:** A PowerShell 5.1 helper discovers registered worktrees through Git, validates manifests and the main installation, and exposes `Prepare`, `Status`, and `Detach`. Compatible Windows worktrees receive a verified directory junction; mismatches detach safely and run worktree-local `npm ci`.

**Tech Stack:** PowerShell 5.1, Git worktrees, Windows NTFS junctions, npm, Python 3.12/pytest.

## Completion Record

- **Task 1:** completed in `ac361bd`; discovery/status contracts passed.
- **Task 2:** completed in `f5d32df`; compatible junction reuse and idempotence passed.
- **Task 3:** completed in `9c7bfcf`; isolated `npm ci` fallback and safe `Detach` passed.
- **Task 4:** completed in `b1b7e81`; workflow docs, policy tests, and timing checks passed.
- **Additional fix:** Git-normalized manifest comparison prevents LF/CRLF false mismatches.
- **Verification:** `50 passed` in `tests/developer_workflow/test_worktree_deps.py`; warm compatible Prepare measured `3.676s` with no repeated tool calls. Initial creation measured `5.771s` because of PowerShell startup and first proof.
- **Dependency contract:** the frontend manifest records npm's lockfile-resolved optional packages explicitly, so a fresh `npm ci` produces a healthy `npm ls` result and compatible worktrees can reuse the primary installation.

---

## File map

- Create `scripts/worktree-deps.ps1`: prepare/status/detach implementation.
- Create `tests/developer_workflow/test_worktree_deps.py`: real temporary worktree and fake-npm contracts.
- Modify `AGENTS.md`: required dependency preparation and cleanup sequence.
- Modify `docs/micro-task-template.md`: concise commands for agents performing isolated tasks.

### Task 1: Worktree discovery and status

**Files:**

- Create: `scripts/worktree-deps.ps1`
- Create: `tests/developer_workflow/test_worktree_deps.py`

- [x] **Step 1: Write failing registration and boundary tests**

```python
def test_status_rejects_main_checkout(worktree_repo):
    main, env = worktree_repo
    result = run_helper(main, env, "Status", main)
    assert result.returncode != 0
    assert "temporary worktree" in combined_output(result).lower()


def test_status_rejects_unregistered_directory(worktree_repo, tmp_path):
    main, env = worktree_repo
    outside = tmp_path / "outside"
    outside.mkdir()
    result = run_helper(main, env, "Status", outside)
    assert result.returncode != 0
    assert "registered worktree" in combined_output(result).lower()


def test_status_rejects_registered_worktree_outside_dot_worktrees(worktree_repo):
    main, env = worktree_repo
    outside = main.parent / "registered-elsewhere"
    create_worktree(main, env, outside)
    result = run_helper(main, env, "Status", outside)
    assert result.returncode != 0
    assert ".worktrees" in combined_output(result)
```

All helper subprocesses use a 60-second timeout and process-tree cleanup from
`tests/developer_workflow/support.py`.

- [x] **Step 2: Verify RED**

Run: `python -m pytest -q tests/developer_workflow/test_worktree_deps.py -k status`

Expected: FAIL because the helper script is absent.

- [x] **Step 3: Implement path discovery and registration**

```powershell
param(
    [ValidateSet("Prepare", "Status", "Detach")]
    [string]$Mode = "Status",
    [string]$WorktreePath = ""
)
$ErrorActionPreference = "Stop"

function Get-FullPath([string]$Path) {
    return [IO.Path]::GetFullPath($Path).TrimEnd("\", "/")
}
function Test-IsWithin([string]$Parent, [string]$Child) {
    $prefix = (Get-FullPath $Parent) + [IO.Path]::DirectorySeparatorChar
    return (Get-FullPath $Child).StartsWith(
        $prefix, [StringComparison]::OrdinalIgnoreCase
    )
}

if (-not $WorktreePath) {
    $WorktreePath = (git rev-parse --show-toplevel).Trim()
}
$targetRoot = Get-FullPath $WorktreePath
$commonValue = (git -C $targetRoot rev-parse --git-common-dir).Trim()
$commonDir = if ([IO.Path]::IsPathRooted($commonValue)) {
    Get-FullPath $commonValue
} else {
    Get-FullPath (Join-Path $targetRoot $commonValue)
}
$mainRoot = Get-FullPath (Split-Path -Parent $commonDir)
$allowedRoot = Join-Path $mainRoot ".worktrees"
if ($targetRoot -eq $mainRoot -or -not (Test-IsWithin $allowedRoot $targetRoot)) {
    throw "Target must be a temporary worktree under $allowedRoot"
}
$registered = Get-RegisteredWorktreePathSet -CommonDirectory $commonDir
if (-not $registered.Contains($targetRoot)) {
    throw "Target is not a registered worktree: $targetRoot"
}
```

`Get-RegisteredWorktreePathSet` must consume
`git --git-dir <common> worktree list --porcelain -z` through a raw byte/NUL
reader and extract only `worktree <path>` fields into a `HashSet[string]`. It
must use ordinal
case-insensitive comparison on Windows and ordinal comparison elsewhere.

- [x] **Step 4: Implement status values**

```powershell
function Get-DependencyState($TargetModules, $MainModules) {
    if (-not (Test-Path -LiteralPath $TargetModules)) {
        return [pscustomobject]@{ Name = "missing"; Target = $null }
    }
    $item = Get-Item -LiteralPath $TargetModules -Force
    $isReparse = [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
    if (-not $isReparse) {
        if ($item.PSIsContainer) {
            return [pscustomobject]@{ Name = "isolated"; Target = $null }
        }
        return [pscustomobject]@{ Name = "unsafe"; Target = $null }
    }
    $resolvedTarget = Get-FullPath ([string]$item.Target)
    if ($resolvedTarget -eq (Get-FullPath $MainModules)) {
        return [pscustomobject]@{ Name = "shared"; Target = $resolvedTarget }
    }
    return [pscustomobject]@{ Name = "unsafe"; Target = $resolvedTarget }
}

$targetModules = Join-Path $targetRoot "frontend/node_modules"
$mainModules = Join-Path $mainRoot "frontend/node_modules"
$state = Get-DependencyState -TargetModules $targetModules -MainModules $mainModules
[pscustomobject]@{
    state = $state.Name
    worktree = $targetRoot
    dependencyPath = $targetModules
    target = $state.Target
} | ConvertTo-Json -Compress
```

States are exactly `missing`, `shared`, `isolated`, and `unsafe`.
A reparse point is `shared` only when its resolved target equals the main
modules path; any other reparse point is `unsafe`. A normal directory is
`isolated`.

- [x] **Step 5: Verify status GREEN and commit**

Run: `python -m pytest -q tests/developer_workflow/test_worktree_deps.py -k status`

Expected: PASS.

```powershell
git add -- scripts/worktree-deps.ps1 tests/developer_workflow/test_worktree_deps.py
git commit -m "feat: inspect worktree dependency state safely"
```

### Task 2: Compatible dependency reuse

**Files:**

- Modify: `scripts/worktree-deps.ps1`
- Modify: `tests/developer_workflow/test_worktree_deps.py`

- [x] **Step 1: Write failing compatibility tests**

```python
@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_prepare_reuses_compatible_main_dependencies(worktree_fixture):
    main, worktree, env, calls = worktree_fixture
    seed_matching_manifests(main, worktree)
    seed_valid_main_modules(main)
    result = run_helper(main, env, "Prepare", worktree)
    assert result.returncode == 0, combined_output(result)
    status = json.loads(run_helper(main, env, "Status", worktree).stdout)
    assert status["state"] == "shared"
    assert Path(status["target"]).resolve() == (main / "frontend/node_modules").resolve()
    assert calls("npm") == []


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_prepare_is_idempotent_for_existing_verified_junction(worktree_fixture):
    main, worktree, env, calls = worktree_fixture
    seed_matching_manifests(main, worktree)
    seed_valid_main_modules(main)
    assert run_helper(main, env, "Prepare", worktree).returncode == 0
    assert run_helper(main, env, "Prepare", worktree).returncode == 0
    assert calls("npm") == []
```

- [x] **Step 2: Verify RED**

Run: `python -m pytest -q tests/developer_workflow/test_worktree_deps.py -k compatible`

Expected: FAIL because `Prepare` has no junction path.

- [x] **Step 3: Implement compatibility proof**

```powershell
function Test-ManifestsMatch($MainRoot, $TargetRoot) {
    foreach ($relative in @("frontend/package.json", "frontend/package-lock.json")) {
        $main = Join-Path $MainRoot $relative
        $target = Join-Path $TargetRoot $relative
        if (-not (Test-Path -LiteralPath $main -PathType Leaf) -or
            -not (Test-Path -LiteralPath $target -PathType Leaf)) { return $false }
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $main).Hash -ne
            (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash) { return $false }
    }
    return $true
}
function Test-MainInstallation($MainRoot) {
    $frontend = Join-Path $MainRoot "frontend"
    if (-not (Test-Path -LiteralPath (Join-Path $frontend "node_modules") -PathType Container)) {
        return $false
    }
    Push-Location $frontend
    try { npm ls --depth=0 --json *> $null; return $LASTEXITCODE -eq 0 }
    finally { Pop-Location }
}
```

Before junction creation, require a runnable `node --version`, matching
manifests, a normal non-reparse main modules directory, and successful
`npm ls --depth=0 --json`.

- [x] **Step 4: Create only the validated junction**

```powershell
if ($state.Name -eq "missing" -and
    (Test-ManifestsMatch $mainRoot $targetRoot) -and
    (Test-MainInstallation $mainRoot)) {
    New-Item -ItemType Junction -Path $targetModules -Target $mainModules |
        Out-Null
    $created = Get-DependencyState $targetModules $mainModules
    if ($created.Name -ne "shared") {
        throw "Created dependency junction did not resolve to the main installation."
    }
    Write-Host "[OK] shared frontend dependencies: $targetModules"
    exit 0
}
```

Do not create parent directories outside the verified target worktree. If the
target path already contains a normal directory, report `isolated` and leave it
unchanged.

- [x] **Step 5: Verify GREEN and commit**

Run: `python -m pytest -q tests/developer_workflow/test_worktree_deps.py -k "compatible or idempotent"`

Expected: PASS on Windows; explicit platform skips elsewhere.

```powershell
git add -- scripts/worktree-deps.ps1 tests/developer_workflow/test_worktree_deps.py
git commit -m "feat: reuse compatible worktree dependencies"
```

### Task 3: Isolated fallback and safe detach

**Files:**

- Modify: `scripts/worktree-deps.ps1`
- Modify: `tests/developer_workflow/test_worktree_deps.py`

- [x] **Step 1: Write failing fallback tests**

```python
@pytest.mark.parametrize("mismatch", ["package", "lock", "missing-main", "invalid-main"])
def test_prepare_uses_isolated_npm_ci_when_reuse_is_unsafe(worktree_fixture, mismatch):
    main, worktree, env, calls = worktree_fixture
    arrange_mismatch(main, worktree, mismatch)
    result = run_helper(main, env, "Prepare", worktree)
    assert result.returncode == 0, combined_output(result)
    assert calls("npm") == [["ci"]]
    status = json.loads(run_helper(main, env, "Status", worktree).stdout)
    assert status["state"] == "isolated"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_manifest_change_detaches_shared_link_before_isolated_install(worktree_fixture):
    main, worktree, env, calls = worktree_fixture
    seed_matching_manifests(main, worktree)
    seed_valid_main_modules(main)
    assert run_helper(main, env, "Prepare", worktree).returncode == 0
    change_worktree_manifest(worktree)
    result = run_helper(main, env, "Prepare", worktree)
    assert result.returncode == 0, combined_output(result)
    assert calls("npm") == [["ci"]]
    assert json.loads(run_helper(main, env, "Status", worktree).stdout)["state"] == "isolated"
```

- [x] **Step 2: Write failing detach safety tests**

```python
@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_detach_removes_link_but_preserves_main_sentinel(worktree_fixture):
    main, worktree, env, _ = worktree_fixture
    seed_matching_manifests(main, worktree)
    sentinel = seed_valid_main_modules(main) / "must-survive.txt"
    sentinel.write_text("safe", encoding="utf-8")
    assert run_helper(main, env, "Prepare", worktree).returncode == 0
    result = run_helper(main, env, "Detach", worktree)
    assert result.returncode == 0, combined_output(result)
    assert not (worktree / "frontend/node_modules").exists()
    assert sentinel.read_text(encoding="utf-8") == "safe"


def test_detach_refuses_normal_directory(worktree_fixture):
    main, worktree, env, _ = worktree_fixture
    modules = worktree / "frontend/node_modules"
    modules.mkdir(parents=True)
    (modules / "owned.txt").write_text("keep", encoding="utf-8")
    result = run_helper(main, env, "Detach", worktree)
    assert result.returncode != 0
    assert (modules / "owned.txt").exists()
```

Add an unexpected-junction-target test and verify both targets remain intact.

- [x] **Step 3: Verify RED**

Run: `python -m pytest -q tests/developer_workflow/test_worktree_deps.py -k "isolated or detach"`

Expected: FAIL because fallback and detach are absent.

- [x] **Step 4: Implement isolated fallback**

When state is `missing` and compatibility fails, or state is `shared` but the
manifests no longer match, call the same validated junction-removal function
used by `Detach` and then run:

```powershell
$frontend = Join-Path $targetRoot "frontend"
Push-Location $frontend
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE" }
}
finally { Pop-Location }
$installed = Get-DependencyState $targetModules $mainModules
if ($installed.Name -ne "isolated") {
    throw "Isolated dependency installation did not create a normal directory."
}
```

If state is already `isolated`, return success without reinstalling. If state
is `unsafe`, fail without invoking npm.

- [x] **Step 5: Implement safe detach**

```powershell
$state = Get-DependencyState $targetModules $mainModules
if ($state.Name -eq "missing") { exit 0 }
if ($state.Name -ne "shared") {
    throw "Detach only removes a verified junction to the main dependency directory."
}
if (-not (Test-IsWithin $targetRoot $targetModules)) {
    throw "Dependency junction escaped the registered worktree."
}
[IO.Directory]::Delete($targetModules, $false)
if (Test-Path -LiteralPath $targetModules) {
    throw "Dependency junction still exists after detach."
}
if (-not (Test-Path -LiteralPath $mainModules -PathType Container)) {
    throw "Main dependency directory disappeared during detach."
}
```

Never call `Remove-Item -Recurse`, `cmd /c rmdir`, or delete the resolved
junction target.

- [x] **Step 6: Verify GREEN and commit**

Run: `python -m pytest -q tests/developer_workflow/test_worktree_deps.py`

Expected: PASS on Windows with explicit junction-only skips elsewhere.

```powershell
git add -- scripts/worktree-deps.ps1 tests/developer_workflow/test_worktree_deps.py
git commit -m "feat: isolate and detach worktree dependencies safely"
```

### Task 4: Workflow documentation and end-to-end timing

**Files:**

- Modify: `AGENTS.md`
- Modify: `docs/micro-task-template.md`
- Modify: `tests/developer_workflow/test_worktree_deps.py`

- [x] **Step 1: Add failing policy assertions**

```python
def test_worktree_policy_requires_dependency_detach_before_cleanup():
    policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "worktree-deps.ps1 -Mode Prepare" in policy
    assert "worktree-deps.ps1 -Mode Detach" in policy
    assert policy.index("-Mode Detach") < policy.index("git worktree remove")


def test_template_forbids_dependency_mutation_while_shared():
    template = (PROJECT_ROOT / "docs/micro-task-template.md").read_text(encoding="utf-8")
    assert "npm install" in template
    assert "npm ci" in template
    assert "shared" in template.lower()
```

- [x] **Step 2: Verify RED**

Run: `python -m pytest -q tests/developer_workflow/test_worktree_deps.py -k policy`

Expected: FAIL because the workflow documents do not include the helper.

- [x] **Step 3: Update the worktree sequence**

Replace the unconditional dependency-install paragraph with these commands and
rules:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/worktree-deps.ps1 -Mode Prepare
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/worktree-deps.ps1 -Mode Status
# Before git worktree remove:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/worktree-deps.ps1 -Mode Detach
```

State explicitly: while status is `shared`, do not run `npm install`,
`npm ci`, or dependency update commands. Detach first when either manifest
changes.

- [x] **Step 4: Measure the compatible path**

Create a disposable registered worktree under `.worktrees/timing-fixture`,
ensure manifests match and main dependencies are valid, then run:

```powershell
Measure-Command {
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/worktree-deps.ps1 -Mode Prepare -WorktreePath .worktrees/timing-fixture
}
```

Expected: under five seconds and no recorded npm invocation. Run `Detach`,
verify the main `node_modules` sentinel remains, then remove the disposable
worktree from the main checkout.

- [x] **Step 5: Verify policy and all dependency contracts**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_worktree_deps.py
git diff --check
```

Expected: PASS.

- [x] **Step 6: Commit documentation**

```powershell
git add -- AGENTS.md docs/micro-task-template.md tests/developer_workflow/test_worktree_deps.py
git commit -m "docs: adopt fast worktree dependency preparation"
```
