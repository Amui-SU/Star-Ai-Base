# Verifiable Container Release Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make manual ECS releases prove that backend, frontend, local routes, public routes, and deployment records all use the same tested 40-character Git SHA.

**Architecture:** Inject the tested SHA into both images, expose it through backend `/health` and frontend `/version.json`, and make `scripts/deploy.sh` verify image references plus local/public version responses before committing deployment state. Preserve exact-SHA manual deployment, transaction recovery, backup, and rollback behavior while rejecting accidental same-SHA redeployments unless explicitly overridden.

**Tech Stack:** FastAPI/Pydantic Settings, Docker and Docker Compose, Nginx static assets, Bash, GitHub Actions, Pytest, Vitest/Next.js verification.

---

## File Structure

- Create `tests/test_application_health.py`: API-level contract for backend build identity.
- Modify `app/config.py`: own the runtime `APP_VERSION` setting.
- Modify `app/main.py`: include the runtime version in `/health`.
- Modify `Dockerfile.backend`: bake the workflow SHA into the backend image default.
- Modify `frontend/Dockerfile`: validate `APP_VERSION` and generate static `/version.json`.
- Modify `compose.production.yml`: inject `IMAGE_TAG` as backend `APP_VERSION`.
- Modify `.github/workflows/publish-images.yml`: pass the SHA to both image builds and emit a manual-release summary.
- Modify `scripts/deploy.sh`: parse `--allow-redeploy`, reject accidental same-SHA deployment, verify running image references, and validate local/public version endpoints during rollout and rollback.
- Modify `tests/test_container_deployment.py`: Dockerfile, Compose, deployment, rollback, and documentation behavior tests.
- Modify `tests/test_ci_workflow.py`: image build-argument and workflow-summary contracts.
- Modify `docs/deployment/container-production.md`: first deploy, normal upgrade, intentional redeploy, rollback, baseline adoption, `IMAGE_TAG`, version checks, and unchanged-page diagnostics.

## Task 0: Create the Isolated Worktree and Confirm the Baseline

**Files:**

- Read: `AGENTS.md`
- Read: `docs/superpowers/specs/2026-07-21-verifiable-container-release-design.md`
- Worktree: `.worktrees/verifiable-container-release`

- [x] **Step 1: Create the implementation worktree**

Run:

```powershell
git status --short --branch
git worktree add -b fix/verifiable-container-release .worktrees\verifiable-container-release main
```

Expected: the main checkout is clean and the new worktree starts at the approved design commit.

- [x] **Step 2: Install frontend dependencies inside the worktree**

Run:

```powershell
npm ci --no-audit --no-fund
```

Working directory: `.worktrees/verifiable-container-release/frontend`

Expected: dependencies install without modifying `package.json` or `package-lock.json`.

- [x] **Step 3: Run the targeted baseline**

Run:

```powershell
python -m pytest -q tests/test_container_deployment.py tests/test_ci_workflow.py
npm --prefix frontend test -- app/page.test.tsx components/chat/__tests__/Composer.interactions.test.tsx
```

Expected: both commands pass before release-flow changes begin.

## Task 1: Expose Backend Build Identity

**Files:**

- Create: `tests/test_application_health.py`
- Modify: `app/config.py`
- Modify: `app/main.py`
- Modify: `Dockerfile.backend`

- [x] **Step 1: Write the failing health-version test**

Create `tests/test_application_health.py`:

```python
import pytest
from pydantic import ValidationError

from app.config import Settings, settings


@pytest.mark.parametrize("version", ["development", "1" * 40])
def test_settings_accept_valid_build_versions(version):
    assert Settings(_env_file=None, app_version=version).app_version == version


def test_settings_rejects_invalid_production_build_version():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_version="latest")


@pytest.mark.asyncio
async def test_health_reports_the_runtime_build_version(client, monkeypatch):
    version = "1" * 40
    monkeypatch.setattr(settings, "app_version", version)

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": version}
```

- [x] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest -q tests/test_application_health.py
```

Expected: FAIL because `Settings` does not expose or validate `app_version` and
`/health` does not return `version`.

- [x] **Step 3: Add the minimal backend version setting and response**

Import `re` and `field_validator`, then add the application setting and
validator in `app/config.py`:

```python
app_version: str = Field(default="development")

@field_validator("app_version")
@classmethod
def validate_app_version(cls, value: str) -> str:
    normalized = value.strip()
    if normalized == "development" or re.fullmatch(r"[0-9a-f]{40}", normalized):
        return normalized
    raise ValueError("APP_VERSION must be 'development' or a 40-character lowercase Git SHA")
```

Change the health route in `app/main.py` to:

```python
@app.get("/health")
async def health_check():
    """Health and immutable build identity for deployment verification."""
    return {"status": "healthy", "version": settings.app_version}
```

Add the build argument near the top of `Dockerfile.backend`:

```dockerfile
ARG APP_VERSION=development

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=$APP_VERSION
```

- [x] **Step 4: Run the focused backend test and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_application_health.py
```

Expected: all backend version tests pass.

- [x] **Step 5: Commit the backend identity slice**

Run:

```powershell
git add tests/test_application_health.py app/config.py app/main.py Dockerfile.backend
git diff --cached --check
git commit -m "feat: expose backend build version"
```

Expected: one commit containing only backend build identity.

## Task 2: Bake the Same SHA into Both Production Images

**Files:**

- Modify: `tests/test_container_deployment.py`
- Modify: `tests/test_ci_workflow.py`
- Modify: `frontend/Dockerfile`
- Modify: `compose.production.yml`
- Modify: `.github/workflows/publish-images.yml`

- [x] **Step 1: Add failing Dockerfile and Compose contracts**

Extend `test_frontend_image_defines_api_url_and_healthcheck_contracts` in `tests/test_container_deployment.py` with:

```python
app_version_arg = "ARG APP_VERSION=development"
app_version_env = "ENV APP_VERSION=$APP_VERSION"
app_version_validation = (
    'RUN test "$APP_VERSION" = development || '
    "printf '%s' \"$APP_VERSION\" | grep -Eq '^[0-9a-f]{40}$'"
)
version_file = (
    "RUN printf '{\"version\":\"%s\"}\\n' \"$APP_VERSION\" "
    "> /app/out/version.json"
)

assert lines.index(app_version_arg) < lines.index(build)
assert lines.index(app_version_env) < lines.index(build)
assert lines.index(app_version_validation) < lines.index(build)
assert lines.index(build) < lines.index(version_file)
```

Extend `test_production_compose_defines_runtime_and_healthcheck_contracts` with:

```python
assert services["backend"]["environment"]["APP_VERSION"] == (
    "${IMAGE_TAG:?set IMAGE_TAG}"
)
```

Add a backend Dockerfile assertion:

```python
def test_backend_image_accepts_the_release_sha_as_app_version():
    lines = active_dockerfile_lines("Dockerfile.backend")

    assert "ARG APP_VERSION=development" in lines
    assert any("APP_VERSION=$APP_VERSION" in line for line in lines)
```

- [x] **Step 2: Add the failing workflow build-argument contract**

In `tests/test_ci_workflow.py`, extend
`test_publish_images_builds_sha_only_then_promotes_both_images_when_current`:

```python
assert content.count("APP_VERSION=${{ env.IMAGE_TAG }}") == 2
```

- [x] **Step 3: Run the focused contracts and verify RED**

Run:

```powershell
python -m pytest -q tests/test_container_deployment.py -k "image or compose"
python -m pytest -q tests/test_ci_workflow.py -k "builds_sha_only"
```

Expected: FAIL because the frontend image, Compose file, and workflow do not yet propagate `APP_VERSION`.

- [x] **Step 4: Generate frontend version metadata and inject backend runtime identity**

Update `frontend/Dockerfile` build stage:

```dockerfile
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG APP_VERSION=development
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV APP_VERSION=$APP_VERSION
RUN test "$APP_VERSION" = development || printf '%s' "$APP_VERSION" | grep -Eq '^[0-9a-f]{40}$'

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build
RUN printf '{"version":"%s"}\n' "$APP_VERSION" > /app/out/version.json
```

Add to the backend `environment` block in `compose.production.yml`:

```yaml
APP_VERSION: "${IMAGE_TAG:?set IMAGE_TAG}"
```

- [x] **Step 5: Pass `APP_VERSION` to both image builds**

Add to the backend build action in `.github/workflows/publish-images.yml`:

```yaml
build-args: |
  APP_VERSION=${{ env.IMAGE_TAG }}
```

Extend the frontend build arguments to:

```yaml
build-args: |
  NEXT_PUBLIC_API_URL=https://zhiku-cloud.cn
  APP_VERSION=${{ env.IMAGE_TAG }}
```

- [x] **Step 6: Run the focused contracts and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_container_deployment.py -k "image or compose"
python -m pytest -q tests/test_ci_workflow.py -k "builds_sha_only"
```

Expected: both commands pass.

- [x] **Step 7: Commit image identity propagation**

Run:

```powershell
git add Dockerfile.backend frontend/Dockerfile compose.production.yml .github/workflows/publish-images.yml tests/test_container_deployment.py tests/test_ci_workflow.py
git diff --cached --check
git commit -m "feat: embed release sha in images"
```

Expected: one commit containing image/Compose/workflow identity propagation and its tests.

## Task 3: Reject Accidental Same-SHA Redeployment

**Files:**

- Modify: `tests/test_container_deployment.py`
- Modify: `scripts/deploy.sh`

- [x] **Step 1: Let the deployment test helper pass explicit CLI arguments**

Change `run_deploy` in `tests/test_container_deployment.py` to:

```python
def run_deploy(
    fixture: dict[str, object],
    *,
    deploy_args: tuple[str, ...] = (TARGET_TAG,),
    **env_updates: str,
) -> subprocess.CompletedProcess:
    env = dict(fixture["env"])
    env.update(env_updates)
    command = 'PATH="$1:$PATH"; export PATH; shift; exec bash "$1" "${@:2}"'
    return subprocess.run(
        [
            bash_executable(),
            "-c",
            command,
            "deploy-test",
            bash_path(Path(fixture["bin_dir"])),
            bash_path(DEPLOY_SCRIPT),
            *deploy_args,
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
```

- [x] **Step 2: Add failing same-SHA behavior tests**

Add:

```python
def test_deploy_script_rejects_same_sha_before_pull(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(TARGET_TAG, encoding="utf-8")

    result = run_deploy(fixture)

    assert result.returncode == 2
    assert "target SHA is already current" in result.stderr
    assert "--allow-redeploy" in result.stderr
    assert not any("|pull " in line for line in log_lines(fixture["docker_log"]))
    assert log_lines(fixture["tar_log"]) == []


def test_deploy_script_allows_explicit_same_sha_redeployment(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(TARGET_TAG, encoding="utf-8")

    result = run_deploy(
        fixture,
        deploy_args=("--allow-redeploy", TARGET_TAG),
        FAKE_EXISTING_SERVICES="backend\nfrontend",
        FAKE_POST_STOP_STATES="exited",
    )

    assert result.returncode == 0, result.stderr
    assert f"{TARGET_TAG}|pull backend frontend" in log_lines(
        fixture["docker_log"]
    )
```

- [x] **Step 3: Run the behavior tests and verify RED**

Run:

```powershell
python -m pytest -q tests/test_container_deployment.py -k "same_sha"
```

Expected: FAIL because the script accepts only one argument and does not reject an already-current target.

- [x] **Step 4: Parse the explicit override and add the guard**

Replace the top-level argument parsing in `scripts/deploy.sh` with:

```bash
ALLOW_REDEPLOY=false
if [[ "${1:-}" == --allow-redeploy ]]; then
  ALLOW_REDEPLOY=true
  shift
fi
if (( $# != 1 )) || [[ ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "usage: $0 [--allow-redeploy] <40-character-git-sha>" >&2
  exit 2
fi
readonly ALLOW_REDEPLOY
readonly TARGET_TAG="$1"
```

After `PREVIOUS_TAG` and `HAS_PREVIOUS` are established, add:

```bash
if [[ "$HAS_PREVIOUS" == true && "$TARGET_TAG" == "$PREVIOUS_TAG" && "$ALLOW_REDEPLOY" == false ]]; then
  echo "target SHA is already current; use --allow-redeploy only for an intentional redeploy" >&2
  exit 2
fi
```

- [x] **Step 5: Run deployment behavior tests and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_container_deployment.py -k "same_sha or allows_fresh_first_deployment or success_tracks_versions"
```

Expected: the new tests and representative existing deploy tests pass.

- [x] **Step 6: Commit same-version protection**

Run:

```powershell
git add scripts/deploy.sh tests/test_container_deployment.py
git diff --cached --check
git commit -m "feat: guard same-sha deployments"
```

Expected: one commit containing only argument parsing, the early guard, and behavior tests.

## Task 4: Verify Image and Endpoint Versions During Rollout and Rollback

**Files:**

- Modify: `tests/test_container_deployment.py`
- Modify: `scripts/deploy.sh`

- [x] **Step 1: Extend the fake Docker and curl boundaries**

Add these fake Compose cases in `deployment_fixture`:

```bash
"ps --format {{.Image}} backend")
  printf '%s/%s/zhiku-backend:%s\n' \
    "$FAKE_ACR_REGISTRY" "$FAKE_ACR_NAMESPACE" \
    "${FAKE_BACKEND_IMAGE_TAG:-$IMAGE_TAG}"
  ;;
"ps --format {{.Image}} frontend")
  printf '%s/%s/zhiku-frontend:%s\n' \
    "$FAKE_ACR_REGISTRY" "$FAKE_ACR_NAMESPACE" \
    "${FAKE_FRONTEND_IMAGE_TAG:-$IMAGE_TAG}"
  ;;
```

Replace the fake curl response body selection with:

```bash
reported_version="${FAKE_REPORTED_VERSION:-${IMAGE_TAG:-development}}"
status=200
body=ok
if [[ "$url" == */health ]]; then
  body="{\"status\":\"healthy\",\"version\":\"$reported_version\"}"
elif [[ "$url" == */version.json ]]; then
  body="{\"version\":\"$reported_version\"}"
fi
if [[ -n "${FAKE_VERSION_MISMATCH_URL:-}" \
  && "$url" == "$FAKE_VERSION_MISMATCH_URL" \
  && "$IMAGE_TAG" == "$FAKE_TARGET_TAG" ]]; then
  body='{"version":"0000000000000000000000000000000000000000"}'
fi
```

Set `FAKE_ACR_REGISTRY`, `FAKE_ACR_NAMESPACE`, and `FAKE_TARGET_TAG` in the
fixture environment to the same test constants used by `.env.deploy`. Limiting
the mismatch to `FAKE_TARGET_TAG` makes the target fail while allowing the
previous SHA to pass rollback attestation.

- [x] **Step 2: Add failing target-version and rollback-version tests**

Add:

```python
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:3000/version.json",
        "https://public.example.test/health",
        "https://public.example.test/version.json",
    ],
)
def test_deploy_script_rolls_back_when_any_runtime_version_mismatches(tmp_path, url):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend\nfrontend",
        FAKE_POST_STOP_STATES="exited",
        FAKE_VERSION_MISMATCH_URL=url,
    )

    assert result.returncode != 0
    commands = log_lines(fixture["docker_log"])
    assert f"{PREVIOUS_TAG}|up -d --pull never backend" in commands
    assert f"{PREVIOUS_TAG}|up -d --pull never frontend" in commands
    assert (deploy_dir / "current-version").read_text().strip() == PREVIOUS_TAG


@pytest.mark.parametrize("service", ["backend", "frontend"])
def test_deploy_script_rejects_a_running_image_with_the_wrong_tag(tmp_path, service):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    image_override = {
        f"FAKE_{service.upper()}_IMAGE_TAG": PREVIOUS_TAG,
    }
    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend\nfrontend",
        FAKE_POST_STOP_STATES="exited",
        **image_override,
    )

    assert result.returncode != 0
    assert f"{service} image mismatch" in result.stderr
```

Extend the rollback health test to require all restored version routes:

```python
for url in [
    "http://127.0.0.1:8000/health",
    "http://127.0.0.1:3000/version.json",
    "https://public.example.test/health",
    "https://public.example.test/version.json",
]:
    assert f"{PREVIOUS_TAG}|{url}" in curl_calls
```

- [x] **Step 3: Run version-verification behavior tests and verify RED**

Run:

```powershell
python -m pytest -q tests/test_container_deployment.py -k "runtime_version or wrong_tag or health_failure"
```

Expected: FAIL because deployment checks only availability and exact legacy health bodies.

- [x] **Step 4: Add robust JSON version verification helpers**

Add `python3` to required commands in `scripts/deploy.sh`:

```bash
for command_name in docker curl python3 tar flock mktemp du df awk; do
```

Add:

```bash
wait_version_json() {
  local url="$1"
  local expected_version="$2"
  local require_healthy="${3:-false}"
  local attempts="${4:-$HTTP_ATTEMPTS}"
  local delay_seconds="${5:-$HTTP_DELAY_SECONDS}"
  local attempt response status body
  local -a curl_options=(
    --fail --silent --show-error --max-time 5
    --write-out $'\n%{http_code}'
  )

  if [[ "$url" == https://* ]]; then
    curl_options+=(--proto '=https' --max-redirs 0)
  fi

  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if response="$(curl "${curl_options[@]}" "$url")"; then
      status="${response##*$'\n'}"
      body="${response%$'\n'*}"
      if [[ "$status" == 200 ]] && BODY="$body" EXPECTED="$expected_version" REQUIRE_HEALTHY="$require_healthy" python3 - 2>/dev/null <<'PY'
import json
import os

body = json.loads(os.environ["BODY"])
assert body.get("version") == os.environ["EXPECTED"]
if os.environ["REQUIRE_HEALTHY"] == "true":
    assert body.get("status") == "healthy"
PY
      then
        return 0
      fi
    fi
    (( attempt == attempts )) || sleep "$delay_seconds"
  done

  echo "version check failed: $url expected $expected_version" >&2
  return 1
}

verify_service_image() {
  local service="$1"
  local expected_version="$2"
  local repository="${ACR_REGISTRY}/${ACR_NAMESPACE}/zhiku-${service}:${expected_version}"
  local actual
  actual="$(compose ps --format '{{.Image}}' "$service")" || return 1
  if [[ "$actual" != "$repository" ]]; then
    echo "$service image mismatch: expected $repository, got ${actual:-none}" >&2
    return 1
  fi
}

verify_runtime_version() {
  local version="$1"
  verify_service_image backend "$version" || return 1
  verify_service_image frontend "$version" || return 1
  wait_version_json "http://127.0.0.1:8000/health" "$version" true || return 1
  wait_version_json "http://127.0.0.1:3000/version.json" "$version" || return 1
  wait_version_json "${PUBLIC_BASE_URL%/}/health" "$version" true || return 1
  wait_version_json "${PUBLIC_BASE_URL%/}/version.json" "$version"
}
```

- [x] **Step 5: Replace availability-only rollout checks**

After starting backend and frontend for the target, use:

```bash
BACKEND_STARTED=true
compose up -d --pull never backend

FRONTEND_STARTED=true
compose up -d --pull never frontend
verify_runtime_version "$TARGET_TAG"
```

In `rollback`, after both services start, use:

```bash
verify_runtime_version "$PREVIOUS_TAG" || return 1
restore_version_state || return 1
```

Keep the existing transaction and backup ordering unchanged.

- [x] **Step 6: Run deployment behavior tests and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_container_deployment.py -k "deploy_script"
```

Expected: all deploy-script structure and behavior tests pass.

- [x] **Step 7: Commit runtime version attestation**

Run:

```powershell
git add scripts/deploy.sh tests/test_container_deployment.py
git diff --cached --check
git commit -m "feat: verify deployed release versions"
```

Expected: one commit containing endpoint/image verification and rollback coverage.

## Task 5: Emit a Copyable Manual Deployment Summary

**Files:**

- Modify: `tests/test_ci_workflow.py`
- Modify: `.github/workflows/publish-images.yml`

- [x] **Step 1: Add the failing workflow-summary contract**

Add to `tests/test_ci_workflow.py`:

```python
def test_publish_images_writes_an_exact_manual_deployment_summary():
    content = read_publish_workflow()
    summary_index = content.index("- name: Write manual deployment summary")
    verify_index = content.index("- name: Verify SHA image revisions")

    assert verify_index < summary_index
    summary = content[summary_index:]
    assert '"$GITHUB_STEP_SUMMARY"' in summary
    assert './scripts/deploy.sh ${IMAGE_TAG}' in summary
    assert 'zhiku-backend:${IMAGE_TAG}' in summary
    assert 'zhiku-frontend:${IMAGE_TAG}' in summary
    assert "ECS has not been deployed" in summary
    assert "/health" in summary
    assert "/version.json" in summary
```

- [x] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest -q tests/test_ci_workflow.py -k "manual_deployment_summary"
```

Expected: FAIL because the workflow does not write `$GITHUB_STEP_SUMMARY`.

- [x] **Step 3: Write the post-publication summary**

Append this step after freshness/promotion handling in
`.github/workflows/publish-images.yml`:

```yaml
- name: Write manual deployment summary
  if: success()
  shell: bash
  run: |
    cat >> "$GITHUB_STEP_SUMMARY" <<EOF
    ## Container images published

    - Tested SHA: \`${IMAGE_TAG}\`
    - Backend: \`${ACR_NAMESPACE}/zhiku-backend:${IMAGE_TAG}\`
    - Frontend: \`${ACR_NAMESPACE}/zhiku-frontend:${IMAGE_TAG}\`

    ECS has not been deployed. Run this manually on the approved host:

    \`\`\`bash
    cd /opt/zhiku-cloud
    ./scripts/deploy.sh ${IMAGE_TAG}
    \`\`\`

    After deployment, verify both \`/health\` and \`/version.json\` report
    \`${IMAGE_TAG}\` locally and publicly.
    EOF
```

Do not print registry credentials or add SSH permissions.

- [x] **Step 4: Run the workflow tests and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_ci_workflow.py
```

Expected: all workflow tests pass.

- [x] **Step 5: Commit the workflow operator handoff**

Run:

```powershell
git add .github/workflows/publish-images.yml tests/test_ci_workflow.py
git diff --cached --check
git commit -m "docs: summarize published release sha"
```

Expected: one commit containing the summary and its contract test.

## Task 6: Rewrite the Production Guide Around Verifiable Releases

**Files:**

- Modify: `tests/test_container_deployment.py`
- Modify: `docs/deployment/container-production.md`

- [x] **Step 1: Add the failing documentation contract**

Add to `tests/test_container_deployment.py`:

```python
def test_production_guide_documents_verifiable_release_operations():
    guide = read("docs/deployment/container-production.md")

    for heading in [
        "## 首次部署",
        "## 正常升级精确 SHA",
        "## 有意重复部署同一 SHA",
        "## 镜像回滚",
        "## 接管已有运行版本",
        "## 页面未变化诊断表",
    ]:
        assert heading in guide

    for required in [
        "./scripts/deploy.sh --allow-redeploy",
        "export IMAGE_TAG=",
        "/version.json",
        "deploy/current-version",
        "Publish Images does not deploy ECS",
        "frontend image mismatch",
    ]:
        assert required in guide
```

- [x] **Step 2: Run the documentation contract and verify RED**

Run:

```powershell
python -m pytest -q tests/test_container_deployment.py -k "verifiable_release_operations"
```

Expected: FAIL because the current guide does not contain the new four-path release structure and version decision table.

- [x] **Step 3: Document the four operational flows**

Restructure the release sections in `docs/deployment/container-production.md`
with these exact headings and commands:

````markdown
## 首次部署

Use a successful `Publish Images` SHA on an empty host:

```bash
cd /opt/zhiku-cloud
test ! -e deploy/transaction || ./scripts/recover-interrupted.sh
./scripts/deploy.sh 0123456789abcdef0123456789abcdef01234567
```

## 正常升级精确 SHA

`Publish Images` does not deploy ECS. Copy the exact SHA from its workflow
summary and run
`./scripts/deploy.sh 0123456789abcdef0123456789abcdef01234567`.

## 有意重复部署同一 SHA

```bash
./scripts/deploy.sh --allow-redeploy 0123456789abcdef0123456789abcdef01234567
```

## 镜像回滚

```bash
ROLLBACK_SHA="$(tr -d '[:space:]' < deploy/previous-version)"
./scripts/deploy.sh "$ROLLBACK_SHA"
```
````

Explain that normal same-SHA deployment is rejected before image pulls.

- [x] **Step 4: Document safe baseline adoption and `IMAGE_TAG` usage**

Add `## 接管已有运行版本`. First explain how to inspect a host that already
has a trusted `current-version` record:

```bash
cd /opt/zhiku-cloud
export IMAGE_TAG="$(tr -d '[:space:]' < deploy/current-version)"
[[ "$IMAGE_TAG" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid current-version" >&2; exit 1; }

docker compose \
  --project-name zhiku-cloud \
  --env-file deploy/.env.deploy \
  -f compose.production.yml ps
```

State explicitly that raw Compose parses all image expressions and therefore
requires `IMAGE_TAG`; operators must not guess or copy an unrelated SHA into
`deploy/current-version`.

For a legacy host with running services but no version record, document this
label-based derivation, which deliberately avoids Compose interpolation:

```bash
cd /opt/zhiku-cloud
BACKEND_IMAGE="$(docker ps \
  --filter label=com.docker.compose.project=zhiku-cloud \
  --filter label=com.docker.compose.service=backend \
  --format '{{.Image}}')"
FRONTEND_IMAGE="$(docker ps \
  --filter label=com.docker.compose.project=zhiku-cloud \
  --filter label=com.docker.compose.service=frontend \
  --format '{{.Image}}')"
BACKEND_SHA="${BACKEND_IMAGE##*:}"
FRONTEND_SHA="${FRONTEND_IMAGE##*:}"

[[ "$BACKEND_SHA" =~ ^[0-9a-f]{40}$ \
  && "$FRONTEND_SHA" == "$BACKEND_SHA" ]] || {
  echo "backend/frontend image tags are not one identical exact SHA" >&2
  exit 1
}

install -d -m 0750 deploy
BASELINE_TMP="$(mktemp deploy/current-version.tmp.XXXXXX)"
printf '%s\n' "$BACKEND_SHA" > "$BASELINE_TMP"
mv -f -- "$BASELINE_TMP" deploy/current-version
```

Explain that empty, ambiguous, non-SHA, or differing image results must stop
the adoption procedure. After recording the baseline, export `IMAGE_TAG` from
the file and run the Compose inspection shown above.

- [x] **Step 5: Add the unchanged-page decision table**

Add:

```markdown
## 页面未变化诊断表

| Evidence                                           | Meaning                             | Next action                                               |
| -------------------------------------------------- | ----------------------------------- | --------------------------------------------------------- |
| `current-version` differs from requested SHA       | Wrong release command or rollback   | Deploy the published target SHA                           |
| Container image tag differs from `current-version` | Compose did not switch the service  | Stop and inspect deployment logs/transaction              |
| Local `/version.json` differs from container tag   | Wrong or stale frontend image       | Verify ACR SHA image revision and pull result             |
| Local version matches but public version differs   | Nginx/DNS points at another runtime | Inspect Nginx upstream, DNS, and proxy cache              |
| Local and public versions match                    | Release is active                   | Hard-refresh only if the browser still shows stale assets |
```

Include a post-deployment checklist for `deploy/current-version`, Compose image
references, local `/health`, local `/version.json`, public `/health`, and public
`/version.json`.

- [x] **Step 6: Run the documentation and deployment contracts**

Run:

```powershell
python -m pytest -q tests/test_container_deployment.py
npx --prefix frontend prettier --check docs/deployment/container-production.md
```

Expected: both commands pass.

- [x] **Step 7: Commit the production guide**

Run:

```powershell
git add docs/deployment/container-production.md tests/test_container_deployment.py
git diff --cached --check
git commit -m "docs: clarify verifiable production releases"
```

Expected: one documentation-focused commit with its contract guard.

## Task 7: Full Verification, Fast-Forward Merge, and Publication

**Files:**

- Verify all changed files from Tasks 1–6.
- Do not stage `frontend/node_modules`, `.next`, caches, secrets, logs, or data.

- [x] **Step 1: Inspect and format the implementation worktree**

Run:

```powershell
git status --short
git diff --check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format
```

Expected: formatting completes without unrelated changes.

- [x] **Step 2: Run the complete commit verification**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1
```

Expected: backend tests, frontend Prettier, ESLint, Vitest, and the production Next.js build all pass.

- [x] **Step 3: Confirm the final diff and clean commit state**

Run:

```powershell
git status --short
git log --oneline main..HEAD
git diff --check main..HEAD
```

Expected: only the approved release-flow files changed and every implementation slice is committed.

- [x] **Step 4: Fast-forward the verified branch into main**

Run from the primary checkout:

```powershell
git status --short --branch
git merge --ff-only fix/verifiable-container-release
```

Expected: `main` advances without a merge commit.

- [x] **Step 5: Re-run targeted release tests on main**

Run:

```powershell
python -m pytest -q tests/test_application_health.py tests/test_ci_workflow.py tests/test_container_deployment.py
```

Expected: all targeted tests pass on `main`.

- [x] **Step 6: Remove the temporary worktree and branch**

After validating the resolved path is under `.worktrees`, run:

```powershell
git worktree remove .worktrees\verifiable-container-release
git branch -d fix/verifiable-container-release
```

Expected: only the primary worktree remains.

- [x] **Step 7: Push only after explicit publication authorization**

Run:

```powershell
git push origin main
```

Expected: the exact verified commit is present on `origin/main`.

- [x] **Step 8: Monitor exact-SHA CI and image publication**

Run:

```powershell
$sha = git rev-parse HEAD
gh run list --commit $sha --json databaseId,workflowName,status,conclusion,url,headSha
```

Expected: `CI` succeeds, then `Publish Images` succeeds for the same full SHA and its summary displays the exact manual ECS command. Do not report ECS deployment merely because images were published.
