# Container Image Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build tested frontend and backend images in GitHub Actions, publish them to Alibaba Cloud ACR, and deploy an exact Git SHA to the Beijing ECS with one command, persistent data, health checks, and image rollback.

**Architecture:** Keep the existing host Nginx and HTTPS configuration as the public gateway. Run the static Next.js export and FastAPI backend as private loopback-only Compose services, while SQLite, Chroma, logs, and production secrets remain in `/opt/zhiku-cloud` on the host. CI publishes immutable SHA-tagged images; a server-side script backs up data, updates the services, verifies internal and public health, and restores the previous image tag if verification fails.

**Tech Stack:** Docker BuildKit, Docker Compose v2, GitHub Actions, Alibaba Cloud ACR, Nginx, Bash, FastAPI, Next.js static export, Pytest.

---

## File Map

- Modify `Dockerfile.backend`: define the production backend image and container health check.
- Modify `frontend/Dockerfile`: bake `NEXT_PUBLIC_API_URL` into the static export and define the frontend health check.
- Modify `.dockerignore`: keep production environment files and deployment data outside image contexts.
- Create `frontend/.dockerignore`: keep frontend-local secrets and generated output outside the independent frontend build context.
- Create `compose.production.yml`: run immutable ACR images with loopback ports, persistent bind mounts, health checks, and log rotation.
- Create `deploy/.env.deploy.example`: document non-secret registry and public URL settings used by Compose and the deploy script.
- Create `scripts/deploy.sh`: validate a SHA, back up persistent data, pull, deploy, verify, and roll back images.
- Create `.github/workflows/publish-images.yml`: publish both images only after the existing `CI` workflow succeeds on a `main` push.
- Create `deploy/nginx/zhiku-cloud.conf.example`: preserve complete API paths, including `/video-notes`, while routing the frontend to port 3000.
- Create `docs/deployment/container-production.md`: document ACR setup, one-time ECS bootstrap, publishing, rollback, backup recovery, and troubleshooting.
- Create `tests/test_container_deployment.py`: enforce the production deployment contract without requiring Docker in the unit-test environment.
- Modify `tests/test_ci_workflow.py`: enforce the CI-to-image-publish gate.
- Modify `README.md`: link the production container deployment runbook from the existing Docker section.

### Task 1: Production Image Contracts

**Files:**

- Modify: `Dockerfile.backend`
- Modify: `frontend/Dockerfile`
- Modify: `.dockerignore`
- Create: `frontend/.dockerignore`
- Create: `tests/test_container_deployment.py`

- [ ] **Step 1: Write failing tests for production image inputs and health checks**

Create `tests/test_container_deployment.py` with:

```python
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_backend_image_has_an_internal_healthcheck():
    content = read("Dockerfile.backend")

    assert "HEALTHCHECK" in content
    assert "http://127.0.0.1:8000/health" in content
    assert "urllib.request" in content


def test_frontend_image_bakes_public_api_url_and_checks_nginx():
    content = read("frontend/Dockerfile")

    assert "ARG NEXT_PUBLIC_API_URL" in content
    assert "ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL" in content
    assert "HEALTHCHECK" in content
    assert "http://127.0.0.1/" in content


def test_production_secrets_and_runtime_data_are_excluded_from_images():
    root_ignore = read(".dockerignore")
    frontend_ignore = read("frontend/.dockerignore")

    for entry in [".env.production", "data/", "logs/", "deploy/.env.deploy"]:
        assert entry in root_ignore
    for entry in [".env.local", ".env.production", "node_modules/", ".next/", "out/"]:
        assert entry in frontend_ignore
```

- [ ] **Step 2: Run the tests and verify the new contract fails**

Run:

```bash
python -m pytest tests/test_container_deployment.py -q
```

Expected: three failures because the Dockerfiles do not yet define health checks or the API build argument, the root ignore file lacks production deployment entries, and `frontend/.dockerignore` is absent.

- [ ] **Step 3: Add the backend image health check**

Replace `Dockerfile.backend` with:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Add the frontend build argument and health check**

Replace `frontend/Dockerfile` with:

```dockerfile
FROM node:22-alpine AS build

WORKDIR /app

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/out /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
```

- [ ] **Step 5: Extend the image ignore list**

Append these lines to `.dockerignore`:

```dockerignore
.env.production
deploy/.env.deploy
deploy/current-version
deploy/previous-version
backups/
```

Create `frontend/.dockerignore`:

```dockerignore
node_modules/
.next/
out/
.env
.env.local
.env.production
.env.*.local
android/**/build/
```

The Dockerfile default remains `http://localhost:8000` so the existing local Compose flow keeps working. Production CI always overrides it with `https://zhiku-cloud.cn`.

- [ ] **Step 6: Run targeted tests and local image builds**

Run:

```bash
python -m pytest tests/test_container_deployment.py -q
docker build -f Dockerfile.backend -t zhiku-backend:plan-check .
docker build --build-arg NEXT_PUBLIC_API_URL=https://zhiku-cloud.cn -f frontend/Dockerfile -t zhiku-frontend:plan-check frontend
```

Expected: three tests pass; both image builds complete successfully; the frontend build output contains the static `/` route.

- [ ] **Step 7: Commit the image contract**

```bash
git add Dockerfile.backend frontend/Dockerfile .dockerignore frontend/.dockerignore tests/test_container_deployment.py
git commit -m "build: harden production container images"
```

### Task 2: Production Compose Contract

**Files:**

- Create: `compose.production.yml`
- Create: `deploy/.env.deploy.example`
- Modify: `tests/test_container_deployment.py`

- [ ] **Step 1: Write failing tests for immutable images, private ports, and persistence**

Append to `tests/test_container_deployment.py`:

```python
def test_production_compose_uses_versioned_images_and_private_ports():
    content = read("compose.production.yml")

    assert "build:" not in content
    assert "${ACR_REGISTRY:?" in content
    assert "${ACR_NAMESPACE:?" in content
    assert content.count("${IMAGE_TAG:?") == 2
    assert '"127.0.0.1:8000:8000"' in content
    assert '"127.0.0.1:3000:80"' in content


def test_production_compose_preserves_data_secrets_and_logs():
    content = read("compose.production.yml")

    assert "./deploy/.env.production" in content
    assert "./data:/app/data" in content
    assert "./logs:/app/logs" in content
    assert "service_healthy" in content
    assert content.count("max-size: \"10m\"") == 2
    assert content.count("max-file: \"5\"") == 2


def test_deploy_environment_example_contains_only_non_secret_settings():
    content = read("deploy/.env.deploy.example")

    assert "ACR_REGISTRY=registry.cn-beijing.aliyuncs.com" in content
    assert "ACR_NAMESPACE=zhiku-cloud" in content
    assert "PUBLIC_BASE_URL=https://zhiku-cloud.cn" in content
    for forbidden in ["PASSWORD=", "SECRET=", "APP_ENCRYPTION_KEY="]:
        assert forbidden not in content
```

- [ ] **Step 2: Run the tests and verify they fail because production assets are absent**

Run:

```bash
python -m pytest tests/test_container_deployment.py -q
```

Expected: the three existing Task 1 tests pass and the three new tests fail with missing-file errors.

- [ ] **Step 3: Create the production Compose file**

Create `compose.production.yml`:

```yaml
name: zhiku-cloud

services:
  backend:
    image: ${ACR_REGISTRY:?set ACR_REGISTRY}/${ACR_NAMESPACE:?set ACR_NAMESPACE}/zhiku-backend:${IMAGE_TAG:?set IMAGE_TAG}
    restart: unless-stopped
    env_file:
      - ./deploy/.env.production
    environment:
      APP_HOST: 0.0.0.0
      APP_PORT: 8000
      DATABASE_URL: sqlite+aiosqlite:///./data/bilibili_rag.db
      CHROMA_PERSIST_DIRECTORY: ./data/chroma_db
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()
      interval: 30s
      timeout: 5s
      start_period: 20s
      retries: 3
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  frontend:
    image: ${ACR_REGISTRY:?set ACR_REGISTRY}/${ACR_NAMESPACE:?set ACR_NAMESPACE}/zhiku-frontend:${IMAGE_TAG:?set IMAGE_TAG}
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
    ports:
      - "127.0.0.1:3000:80"
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1/"]
      interval: 30s
      timeout: 5s
      start_period: 10s
      retries: 3
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
```

The production file stays at repository root. On the server it is copied to `/opt/zhiku-cloud/compose.production.yml`, so the relative `data`, `logs`, and `deploy/.env.production` paths resolve under `/opt/zhiku-cloud`.

- [ ] **Step 4: Create the deployment environment example**

Create `deploy/.env.deploy.example`:

```dotenv
ACR_REGISTRY=registry.cn-beijing.aliyuncs.com
ACR_NAMESPACE=zhiku-cloud
PUBLIC_BASE_URL=https://zhiku-cloud.cn
```

The operator changes `ACR_NAMESPACE` if the namespace created in ACR differs. No registry password belongs in this file; the server performs `docker login` once and Docker stores its own credential entry.

- [ ] **Step 5: Validate tests and Compose interpolation**

Run:

```bash
python -m pytest tests/test_container_deployment.py -q
IMAGE_TAG=0123456789abcdef0123456789abcdef01234567 docker compose --env-file deploy/.env.deploy.example -f compose.production.yml config --quiet
```

Expected: six tests pass and Compose exits with code 0 without printing a rendered configuration error.

- [ ] **Step 6: Commit the production Compose contract**

```bash
git add compose.production.yml deploy/.env.deploy.example tests/test_container_deployment.py
git commit -m "build: add production compose deployment"
```

### Task 3: Safe Deploy and Image Rollback Script

**Files:**

- Create: `scripts/deploy.sh`
- Modify: `tests/test_container_deployment.py`

- [ ] **Step 1: Write failing tests for deploy safety boundaries**

Append to `tests/test_container_deployment.py`:

```python
def test_deploy_script_validates_versions_and_never_deletes_volumes():
    content = read("scripts/deploy.sh")

    assert "^[0-9a-f]{40}$" in content
    assert "docker compose" in content
    assert "compose pull backend frontend" in content
    assert "compose up -d backend" in content
    assert "compose up -d frontend" in content
    assert "docker compose down -v" not in content
    assert "ACR_PASSWORD" not in content


def test_deploy_script_backs_up_and_tracks_successful_versions():
    content = read("scripts/deploy.sh")

    assert 'tar -C "$DATA_DIR" -czf "$BACKUP_DIR/data.tar.gz" .' in content
    assert "current-version" in content
    assert "previous-version" in content
    assert "rollback" in content
    assert 'wait_http "http://127.0.0.1:8000/health"' in content
    assert 'wait_http "http://127.0.0.1:3000/"' in content
    assert 'wait_http "${PUBLIC_BASE_URL%/}/health"' in content
```

- [ ] **Step 2: Run the tests and verify missing script failures**

Run:

```bash
python -m pytest tests/test_container_deployment.py -q
```

Expected: the six earlier tests pass and the two new tests fail because `scripts/deploy.sh` does not exist.

- [ ] **Step 3: Implement the deployment script**

Create `scripts/deploy.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_TAG="${1:-}"
if [[ ! "$TARGET_TAG" =~ ^[0-9a-f]{40}$ ]]; then
  echo "usage: $0 <40-character-git-sha>" >&2
  exit 2
fi

DEPLOY_ROOT="${ZHIKU_DEPLOY_ROOT:-/opt/zhiku-cloud}"
COMPOSE_FILE="$DEPLOY_ROOT/compose.production.yml"
DEPLOY_DIR="$DEPLOY_ROOT/deploy"
DEPLOY_ENV="$DEPLOY_DIR/.env.deploy"
APP_ENV="$DEPLOY_DIR/.env.production"
DATA_DIR="$DEPLOY_ROOT/data"
LOG_DIR="$DEPLOY_ROOT/logs"
BACKUPS_DIR="$DEPLOY_ROOT/backups"
CURRENT_FILE="$DEPLOY_DIR/current-version"
PREVIOUS_FILE="$DEPLOY_DIR/previous-version"

for command_name in docker curl tar; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "missing required command: $command_name" >&2
    exit 3
  }
done

for required_file in "$COMPOSE_FILE" "$DEPLOY_ENV" "$APP_ENV"; do
  [[ -f "$required_file" ]] || {
    echo "missing required deployment file: $required_file" >&2
    exit 4
  }
done

set -a
# shellcheck disable=SC1090
source "$DEPLOY_ENV"
set +a
: "${ACR_REGISTRY:?set ACR_REGISTRY in .env.deploy}"
: "${ACR_NAMESPACE:?set ACR_NAMESPACE in .env.deploy}"
: "${PUBLIC_BASE_URL:?set PUBLIC_BASE_URL in .env.deploy}"

export ACR_REGISTRY ACR_NAMESPACE
IMAGE_TAG="$TARGET_TAG"
export IMAGE_TAG

mkdir -p "$DEPLOY_DIR" "$DATA_DIR" "$LOG_DIR" "$BACKUPS_DIR"

compose() {
  docker compose \
    --project-directory "$DEPLOY_ROOT" \
    --env-file "$DEPLOY_ENV" \
    -f "$COMPOSE_FILE" \
    "$@"
}

wait_http() {
  local url="$1"
  local attempts="${2:-30}"
  local delay_seconds="${3:-2}"
  local attempt

  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if curl --fail --silent --show-error --max-time 5 "$url" >/dev/null; then
      return 0
    fi
    sleep "$delay_seconds"
  done

  echo "health check failed: $url" >&2
  return 1
}

PREVIOUS_TAG=""
if [[ -f "$CURRENT_FILE" ]]; then
  PREVIOUS_TAG="$(tr -d '[:space:]' < "$CURRENT_FILE")"
fi

DEPLOY_STARTED=false

rollback() {
  if [[ ! "$PREVIOUS_TAG" =~ ^[0-9a-f]{40}$ ]]; then
    echo "no previous image tag is available for automatic rollback" >&2
    return 1
  fi

  echo "rolling back images to $PREVIOUS_TAG" >&2
  IMAGE_TAG="$PREVIOUS_TAG"
  export IMAGE_TAG
  compose up -d backend
  wait_http "http://127.0.0.1:8000/health"
  compose up -d frontend
  wait_http "http://127.0.0.1:3000/"
  wait_http "${PUBLIC_BASE_URL%/}/health"
}

on_error() {
  local exit_code="$?"
  trap - ERR
  if [[ "$DEPLOY_STARTED" == true ]]; then
    rollback || echo "automatic image rollback failed; inspect docker compose logs" >&2
  fi
  exit "$exit_code"
}
trap on_error ERR

echo "pulling image tag $TARGET_TAG"
compose pull backend frontend

if compose ps --status running --services | grep -qx backend; then
  compose stop backend
fi
DEPLOY_STARTED=true

BACKUP_DIR="$BACKUPS_DIR/$(date -u +%Y%m%dT%H%M%SZ)-$TARGET_TAG"
mkdir -p "$BACKUP_DIR"
tar -C "$DATA_DIR" -czf "$BACKUP_DIR/data.tar.gz" .
printf '%s\n' "$PREVIOUS_TAG" > "$BACKUP_DIR/previous-image-tag"

IMAGE_TAG="$TARGET_TAG"
export IMAGE_TAG
compose up -d backend
wait_http "http://127.0.0.1:8000/health"

compose up -d frontend
wait_http "http://127.0.0.1:3000/"
wait_http "${PUBLIC_BASE_URL%/}/"
wait_http "${PUBLIC_BASE_URL%/}/health"

if [[ "$PREVIOUS_TAG" =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' "$PREVIOUS_TAG" > "$PREVIOUS_FILE"
fi
printf '%s\n' "$TARGET_TAG" > "$CURRENT_FILE.tmp"
mv "$CURRENT_FILE.tmp" "$CURRENT_FILE"

trap - ERR
echo "deployment succeeded: $TARGET_TAG"
```

- [ ] **Step 4: Validate syntax and contract tests**

Run:

```bash
bash -n scripts/deploy.sh
python -m pytest tests/test_container_deployment.py -q
```

Expected: Bash exits with code 0 and all eight deployment tests pass.

- [ ] **Step 5: Exercise validation without touching Docker state**

Run:

```bash
bash scripts/deploy.sh invalid-tag
```

Expected: exit code 2 and `usage: scripts/deploy.sh <40-character-git-sha>`. Because validation occurs before Docker commands, no container or file is changed.

- [ ] **Step 6: Commit the deploy script**

```bash
git add scripts/deploy.sh tests/test_container_deployment.py
git commit -m "ops: add versioned container deploy script"
```

### Task 4: Publish Images After CI Success

**Files:**

- Create: `.github/workflows/publish-images.yml`
- Modify: `tests/test_ci_workflow.py`

- [ ] **Step 1: Write a failing workflow contract test**

Append to `tests/test_ci_workflow.py`:

```python
def test_image_publish_waits_for_ci_and_uses_the_tested_commit_sha():
    project_root = Path(__file__).resolve().parents[1]
    workflow = project_root / ".github" / "workflows" / "publish-images.yml"

    assert workflow.exists()
    content = workflow.read_text(encoding="utf-8")
    for required in [
        "workflow_run:",
        'workflows: ["CI"]',
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'push'",
        "github.event.workflow_run.head_sha",
        "secrets.ACR_REGISTRY",
        "secrets.ACR_USERNAME",
        "secrets.ACR_PASSWORD",
        "vars.ACR_NAMESPACE",
        "Dockerfile.backend",
        "frontend/Dockerfile",
        "NEXT_PUBLIC_API_URL=https://zhiku-cloud.cn",
        "zhiku-backend:latest",
        "zhiku-frontend:latest",
    ]:
        assert required in content
```

- [ ] **Step 2: Run the test and verify it fails on the missing workflow**

Run:

```bash
python -m pytest tests/test_ci_workflow.py -q
```

Expected: existing CI tests pass and the new workflow test fails because `publish-images.yml` is absent.

- [ ] **Step 3: Create the image publishing workflow**

Create `.github/workflows/publish-images.yml`:

```yaml
name: Publish Images

on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]
    branches: [main]

permissions:
  contents: read

jobs:
  publish:
    if: github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.event == 'push'
    runs-on: ubuntu-latest
    env:
      ACR_REGISTRY: ${{ secrets.ACR_REGISTRY }}
      ACR_NAMESPACE: ${{ vars.ACR_NAMESPACE }}
      IMAGE_TAG: ${{ github.event.workflow_run.head_sha }}
    steps:
      - name: Check out the tested commit
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.workflow_run.head_sha }}

      - name: Log in to Alibaba Cloud ACR
        uses: docker/login-action@f4ef78c080cd8ba55a85445d5b36e214a81df20a
        with:
          registry: ${{ secrets.ACR_REGISTRY }}
          username: ${{ secrets.ACR_USERNAME }}
          password: ${{ secrets.ACR_PASSWORD }}

      - name: Build and push backend image
        uses: docker/build-push-action@3b5e8027fcad23fda98b2e3ac259d8d67585f671
        with:
          context: .
          file: ./Dockerfile.backend
          push: true
          tags: |
            ${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-backend:${{ env.IMAGE_TAG }}
            ${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-backend:latest
          cache-from: type=gha,scope=backend
          cache-to: type=gha,mode=max,scope=backend

      - name: Build and push frontend image
        uses: docker/build-push-action@3b5e8027fcad23fda98b2e3ac259d8d67585f671
        with:
          context: ./frontend
          file: ./frontend/Dockerfile
          push: true
          build-args: |
            NEXT_PUBLIC_API_URL=https://zhiku-cloud.cn
          tags: |
            ${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-frontend:${{ env.IMAGE_TAG }}
            ${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-frontend:latest
          cache-from: type=gha,scope=frontend
          cache-to: type=gha,mode=max,scope=frontend
```

The Docker Actions are pinned to full commits from GitHub's official image publishing example. The implementation review must check upstream release notes before changing those pins.

- [ ] **Step 4: Run workflow contract tests**

Run:

```bash
python -m pytest tests/test_ci_workflow.py tests/test_container_deployment.py -q
```

Expected: all CI and deployment contract tests pass.

- [ ] **Step 5: Commit the publishing workflow**

```bash
git add .github/workflows/publish-images.yml tests/test_ci_workflow.py
git commit -m "ci: publish versioned images to acr"
```

### Task 5: Nginx Integration and Production Runbook

**Files:**

- Create: `deploy/nginx/zhiku-cloud.conf.example`
- Create: `docs/deployment/container-production.md`
- Modify: `README.md`
- Modify: `tests/test_container_deployment.py`

- [ ] **Step 1: Write failing tests for API coverage and runbook safety**

Append to `tests/test_container_deployment.py`:

```python
def test_nginx_example_routes_all_backend_prefixes_and_keeps_ports_private():
    content = read("deploy/nginx/zhiku-cloud.conf.example")

    for prefix in [
        "health",
        "system-auth",
        "api-accounts",
        "chat",
        "knowledge-bases",
        "local-connection",
        "source-bindings",
        "imports",
        "auth",
        "favorites",
        "knowledge",
        "video-notes",
    ]:
        assert prefix in content
    assert "http://127.0.0.1:8000" in content
    assert "http://127.0.0.1:3000" in content
    assert "limit_req zone=send_code_per_ip" in content


def test_production_runbook_documents_bootstrap_publish_and_recovery():
    content = read("docs/deployment/container-production.md")

    for required in [
        "ACR_REGISTRY",
        "ACR_USERNAME",
        "ACR_PASSWORD",
        "ACR_NAMESPACE",
        "/opt/zhiku-cloud",
        ".env.production",
        "docker login",
        "scripts/deploy.sh",
        "current-version",
        "previous-version",
        "data.tar.gz",
        "nginx -t",
        "docker compose logs",
    ]:
        assert required in content
    assert "docker compose down -v" not in content
```

- [ ] **Step 2: Run tests and verify missing documentation failures**

Run:

```bash
python -m pytest tests/test_container_deployment.py -q
```

Expected: the eight earlier tests pass and the two new tests fail because the Nginx example and runbook do not exist.

- [ ] **Step 3: Create the Nginx production example**

Create `deploy/nginx/zhiku-cloud.conf.example`:

```nginx
# Place this directive in the nginx http {} block, outside server {}.
limit_req_zone $binary_remote_addr zone=send_code_per_ip:10m rate=3r/m;

server {
    listen 80;
    server_name zhiku-cloud.cn www.zhiku-cloud.cn;
    return 301 https://zhiku-cloud.cn$request_uri;
}

server {
    listen 443 ssl http2;
    server_name zhiku-cloud.cn www.zhiku-cloud.cn;

    # Keep the certificate paths already issued on the ECS.
    ssl_certificate /etc/nginx/ssl/zhiku-cloud.cn/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/zhiku-cloud.cn/privkey.pem;

    client_max_body_size 2g;

    location = /system-auth/send-code {
        limit_req zone=send_code_per_ip burst=2 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location ~ ^/(health|docs|redoc|openapi\.json|system-auth|api-accounts|chat|knowledge-bases|local-connection|source-bindings|imports|auth|favorites|knowledge|video-notes)(/|$) {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The runbook must tell the operator to preserve the certificate paths from the active server configuration if they differ from the example.

- [ ] **Step 4: Write the production runbook**

Create `docs/deployment/container-production.md` with these complete sections and commands:

````markdown
# 容器镜像生产部署

## 一次性准备

在阿里云 ACR 北京地域创建私有命名空间 `zhiku-cloud`，并创建 `zhiku-backend`、`zhiku-frontend` 两个私有仓库。

在 GitHub 仓库的 Actions secrets 中配置 `ACR_REGISTRY`、`ACR_USERNAME`、`ACR_PASSWORD`，在 Actions variable 中配置 `ACR_NAMESPACE=zhiku-cloud`。

服务器安装 Docker Engine 与 Compose v2 后创建目录：

```bash
sudo install -d -m 0750 /opt/zhiku-cloud/{deploy,data,logs,backups}
sudo cp compose.production.yml /opt/zhiku-cloud/compose.production.yml
sudo cp deploy/.env.deploy.example /opt/zhiku-cloud/deploy/.env.deploy
sudo cp .env.example /opt/zhiku-cloud/deploy/.env.production
sudo install -m 0750 scripts/deploy.sh /opt/zhiku-cloud/deploy/deploy.sh
sudo chmod 0600 /opt/zhiku-cloud/deploy/.env.deploy /opt/zhiku-cloud/deploy/.env.production
```
````

编辑 `.env.production` 写入 SMTP、OAuth、管理员邮箱和 `APP_ENCRYPTION_KEY`。编辑 `.env.deploy`，确保 ACR namespace 与控制台一致。不要把两个生产文件提交到 Git。

登录一次私有仓库：

```bash
docker login registry.cn-beijing.aliyuncs.com
```

## 发布

本地提交并推送：

```bash
git push origin main
```

等待 `CI` 和 `Publish Images` 成功，从 GitHub 提交页面复制完整 40 位 SHA，在服务器执行：

```bash
/opt/zhiku-cloud/deploy/deploy.sh 0123456789abcdef0123456789abcdef01234567
```

脚本会拉取镜像、停止后端写入、将 `data` 打包为 `backups/<时间>-<SHA>/data.tar.gz`、启动新后端和前端，并检查本机端口及 `https://zhiku-cloud.cn/health`。

## Nginx

将 `deploy/nginx/zhiku-cloud.conf.example` 中的 API 和前端 location 合并到现有 HTTPS 配置，保留服务器当前证书路径。确保 `/video-notes` 进入 8000，页面进入 3000。修改后执行：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 查看状态

```bash
cd /opt/zhiku-cloud
docker compose --env-file deploy/.env.deploy -f compose.production.yml ps
docker compose --env-file deploy/.env.deploy -f compose.production.yml logs --tail=200 backend frontend
cat deploy/current-version
cat deploy/previous-version
curl -fsS https://zhiku-cloud.cn/health
```

## 镜像回滚

读取 `previous-version`，将其中的 SHA 传给同一个脚本：

```bash
/opt/zhiku-cloud/deploy/deploy.sh "$(cat /opt/zhiku-cloud/deploy/previous-version)"
```

镜像回滚不会自动恢复数据。如果新版本写入了不兼容数据，先停止后端，将对应备份的 `data.tar.gz` 解压到一个空的临时目录，检查内容后再人工替换 `/opt/zhiku-cloud/data`。

## 故障排查

镜像拉取失败时重新执行 `docker login`，并检查 ACR registry、namespace 和仓库名称。接口返回静态 404 时运行 `sudo nginx -T`，确认 `/video-notes` 等 API location 位于 `location /` 前且代理到 8000。容器不健康时使用 `docker compose logs` 查看启动错误，并确认 `/opt/zhiku-cloud/data` 与 `/opt/zhiku-cloud/logs` 可写。

````

- [ ] **Step 5: Link the runbook from README**

Immediately after the existing `docker compose up --build` example in `README.md`, add:

```markdown
生产服务器推荐使用 ACR 版本镜像和一键部署脚本，不在 ECS 上重复构建。完整步骤见 [容器镜像生产部署](docs/deployment/container-production.md)。
````

- [ ] **Step 6: Run documentation and deployment contract tests**

Run:

```bash
python -m pytest tests/test_container_deployment.py tests/test_readme_links.py -q
```

Expected: all deployment tests and README link checks pass.

- [ ] **Step 7: Commit the production operations documentation**

```bash
git add deploy/nginx/zhiku-cloud.conf.example docs/deployment/container-production.md README.md tests/test_container_deployment.py
git commit -m "docs: add container production runbook"
```

### Task 6: End-to-End Verification and First Release Checklist

**Files:**

- Modify only if verification exposes a defect in the files created by Tasks 1-5.

- [ ] **Step 1: Run backend deployment and CI contract tests**

```bash
python -m pytest tests/test_docker_support.py tests/test_container_deployment.py tests/test_ci_workflow.py tests/test_readme_links.py -q
```

Expected: all selected tests pass with no warnings introduced by the new files.

- [ ] **Step 2: Run the full backend suite**

```bash
python -m pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 3: Run frontend quality gates**

```bash
cd frontend
npm ci
npm run lint
npm test
NEXT_PUBLIC_API_URL=https://zhiku-cloud.cn npm run build
cd ..
```

Expected: Lint, Vitest, TypeScript, and static export finish with exit code 0. If the existing Vitest suite hits machine-wide 5-second timeouts, rerun the failed files individually and record the full-suite limitation instead of increasing unrelated test timeouts in this deployment change.

- [ ] **Step 4: Validate Docker and Compose artifacts**

```bash
docker build -f Dockerfile.backend -t zhiku-backend:verification .
docker build --build-arg NEXT_PUBLIC_API_URL=https://zhiku-cloud.cn -f frontend/Dockerfile -t zhiku-frontend:verification frontend
IMAGE_TAG=0123456789abcdef0123456789abcdef01234567 docker compose --env-file deploy/.env.deploy.example -f compose.production.yml config --quiet
bash -n scripts/deploy.sh
```

Expected: both images build, Compose validates, and Bash syntax validation exits with code 0.

- [ ] **Step 5: Verify image contents locally**

```bash
docker run --rm -d --name zhiku-backend-check -p 127.0.0.1:18000:8000 zhiku-backend:verification
curl --retry 20 --retry-delay 2 --retry-connrefused -fsS http://127.0.0.1:18000/health
docker rm -f zhiku-backend-check

docker run --rm -d --name zhiku-frontend-check -p 127.0.0.1:13000:80 zhiku-frontend:verification
curl --retry 10 --retry-delay 1 --retry-connrefused -fsS http://127.0.0.1:13000/
docker rm -f zhiku-frontend-check
```

Expected: backend returns `{"status":"healthy"}` and the frontend returns its generated HTML. Cleanup removes only the two explicitly named verification containers.

- [ ] **Step 6: Push and configure ACR only after local verification**

Push the implementation commits to `main`. In GitHub, verify `CI` succeeds before `Publish Images`, then confirm ACR contains both the full commit SHA and `latest` tags for both repositories.

- [ ] **Step 7: Perform the first ECS deployment manually**

Follow `docs/deployment/container-production.md`. Before running `deploy.sh`, confirm `/opt/zhiku-cloud/data`, `/opt/zhiku-cloud/logs`, `.env.production`, and the active Nginx certificate paths. After deployment verify:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:3000/
curl -fsS https://zhiku-cloud.cn/health
curl -fsS -o /dev/null -w '%{http_code}\n' https://zhiku-cloud.cn/video-notes
```

Expected: the first three checks return success; `/video-notes` reaches FastAPI and may return an authentication or method response, but must not return the frontend Nginx static 404 page.

- [ ] **Step 8: Perform a rollback rehearsal**

After two successful SHA deployments exist, deploy the value in `previous-version`, confirm public health, then deploy the newest SHA again. Verify `data` survives both container replacements and each deployment creates a backup directory.

- [ ] **Step 9: Record verification evidence**

Add the commands, exit codes, image digests, deployed SHA, backup path, and rollback rehearsal result to the deployment change summary or pull request. Do not write registry passwords, app secrets, or the contents of `.env.production`.

## Implementation Notes

- Keep the existing `docker-compose.yml` unchanged as the local development entry point.
- Do not add SSH auto-deploy in this implementation. The first production phase ends with CI-published images and a manual one-command server deployment.
- Do not use `latest` in `compose.production.yml`; it exists only as a convenience tag in ACR.
- Do not add ACR or application credentials to repository files, Docker build arguments, image labels, test output, or deployment logs.
- Do not run volume-removing Compose commands. Image rollback and data recovery remain separate operations.
