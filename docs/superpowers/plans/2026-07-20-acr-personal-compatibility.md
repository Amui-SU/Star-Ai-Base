# ACR Personal Edition Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow production deployment to use an Alibaba Cloud ACR Personal Edition public endpoint in Beijing without weakening SHA-tag deployment, revision verification, backup, or rollback.

**Architecture:** Keep `production-preflight.sh` as the shared registry trust boundary for deploy and restore. Expand only its strict Beijing ACR allowlist; keep publication write-once for existing SHA tags and retain OCI revision checks before `latest` promotion.

**Tech Stack:** Bash, Docker Compose, GitHub Actions YAML, pytest, PyYAML, Markdown

---

## File Map

- `scripts/production-preflight.sh`: validate supported Beijing ACR endpoints.
- `deploy/.env.deploy.example`: show the selected Personal endpoint.
- `tests/test_container_deployment.py`: behavior and runbook contracts.
- `.github/workflows/publish-images.yml`: edition-neutral SHA step names.
- `tests/test_ci_workflow.py`: publication ordering and safeguards.
- `docs/deployment/container-production.md`: limitations and controls.

### Task 1: Expand The Registry Trust Boundary

**Files:**

- Modify: `tests/test_container_deployment.py:21-22`
- Modify: `tests/test_container_deployment.py:346-352`
- Modify: `tests/test_container_deployment.py:1020-1050`
- Modify: `scripts/production-preflight.sh:15-65`
- Modify: `deploy/.env.deploy.example:1`

- [ ] **Step 1: Write failing acceptance tests**

Add these constants and behavior test:

```python
PERSONAL_ACR = "crpi-test123.cn-beijing.personal.cr.aliyuncs.com"
LEGACY_PERSONAL_ACR = "registry.cn-beijing.aliyuncs.com"


@pytest.mark.parametrize(
    "registry",
    [ENTERPRISE_ACR, PERSONAL_ACR, LEGACY_PERSONAL_ACR],
)
def test_deploy_script_accepts_supported_beijing_acr_public_endpoints(
    tmp_path, registry
):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / ".env.deploy").write_text(
        f"ACR_REGISTRY={registry}\n"
        "ACR_NAMESPACE=zhiku\n"
        "PUBLIC_BASE_URL=https://public.example.test\n",
        encoding="utf-8",
    )
    result = run_deploy(fixture)
    assert result.returncode == 0, result.stderr
```

Replace the Enterprise-only source contract with:

```python
def test_deploy_script_requires_supported_beijing_acr_public_endpoint():
    content = read("scripts/production-preflight.sh")
    assert "cn-beijing\\.cr\\.aliyuncs\\.com" in content
    assert "cn-beijing\\.personal\\.cr\\.aliyuncs\\.com" in content
    assert "registry.cn-beijing.aliyuncs.com" in content
    assert "supported Beijing ACR public endpoint" in content
```

- [ ] **Step 2: Define rejected endpoints**

Replace the old rejection parametrization with:

```python
@pytest.mark.parametrize(
    "registry",
    [
        "registry-vpc.cn-beijing.aliyuncs.com",
        "registry.cn-beijing.cr.aliyuncs.com",
        "test-instance-registry.cn-hangzhou.cr.aliyuncs.com",
        "crpi-test123.cn-hangzhou.personal.cr.aliyuncs.com",
        "crpi-test123-vpc.cn-beijing.personal.cr.aliyuncs.com",
        "docker.io",
        "https://crpi-test123.cn-beijing.personal.cr.aliyuncs.com",
        "your-instance-registry.cn-beijing.cr.aliyuncs.com",
        "crpi-your-instance.cn-beijing.personal.cr.aliyuncs.com",
    ],
)
def test_deploy_script_rejects_unsupported_or_placeholder_acr_before_docker(
    tmp_path, registry
):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / ".env.deploy").write_text(
        f"ACR_REGISTRY={registry}\n"
        "ACR_NAMESPACE=zhiku\n"
        "PUBLIC_BASE_URL=https://public.example.test\n",
        encoding="utf-8",
    )
    result = run_deploy(fixture)
    assert result.returncode != 0
    assert "invalid deployment environment" in result.stderr
    assert log_lines(fixture["docker_log"]) == []
```

- [ ] **Step 3: Run tests and verify RED**

```powershell
python -m pytest tests/test_container_deployment.py::test_deploy_script_requires_supported_beijing_acr_public_endpoint tests/test_container_deployment.py::test_deploy_script_accepts_supported_beijing_acr_public_endpoints tests/test_container_deployment.py::test_deploy_script_rejects_unsupported_or_placeholder_acr_before_docker -q
```

Expected: Personal acceptance and the new contract fail because the preflight is Enterprise-only.

- [ ] **Step 4: Implement the strict allowlist**

Declare `local supported_registry=false` with the existing local booleans, then replace the Enterprise-only validation with:

```bash
  if [[ "$seen_registry" == true ]]; then
    if [[ "$ACR_REGISTRY" =~ ^[a-z0-9][a-z0-9-]*-registry\.cn-beijing\.cr\.aliyuncs\.com$ ]]; then
      supported_registry=true
    elif [[ "$ACR_REGISTRY" =~ ^crpi-[a-z0-9][a-z0-9-]*\.cn-beijing\.personal\.cr\.aliyuncs\.com$ ]] &&
      [[ ! "$ACR_REGISTRY" =~ ^crpi-.*-vpc\.cn-beijing\.personal\.cr\.aliyuncs\.com$ ]]; then
      supported_registry=true
    elif [[ "$ACR_REGISTRY" == "registry.cn-beijing.aliyuncs.com" ]]; then
      supported_registry=true
    fi
  fi
  [[ "$supported_registry" == true ]] ||
    production_preflight_invalid_deploy "ACR_REGISTRY must be a supported Beijing ACR public endpoint"
  [[ "$ACR_REGISTRY" != "your-instance-registry.cn-beijing.cr.aliyuncs.com" &&
    "$ACR_REGISTRY" != "crpi-your-instance.cn-beijing.personal.cr.aliyuncs.com" ]] ||
    production_preflight_invalid_deploy "ACR_REGISTRY still contains an example placeholder"
```

Set the example:

```dotenv
ACR_REGISTRY=crpi-your-instance.cn-beijing.personal.cr.aliyuncs.com
```

- [ ] **Step 5: Run focused shared-preflight tests**

```powershell
python -m pytest tests/test_container_deployment.py::test_deploy_script_requires_supported_beijing_acr_public_endpoint tests/test_container_deployment.py::test_deploy_script_accepts_supported_beijing_acr_public_endpoints tests/test_container_deployment.py::test_deploy_script_rejects_unsupported_or_placeholder_acr_before_docker tests/test_container_deployment.py::test_deploy_and_restore_share_one_read_only_production_preflight tests/test_container_deployment.py::test_restore_script_reuses_production_preflight_before_staging_or_downtime -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add scripts/production-preflight.sh deploy/.env.deploy.example tests/test_container_deployment.py
git commit -m "feat: support ACR personal endpoints"
```

### Task 2: Make Image Publication Edition-Neutral

**Files:**

- Modify: `tests/test_ci_workflow.py:106-200`
- Modify: `.github/workflows/publish-images.yml:48-132`

- [ ] **Step 1: Write failing workflow assertions**

Replace all test lookups for the old names with:

```python
inspect_index = content.index("- name: Inspect SHA tags")
verify_index = content.index("- name: Verify SHA image revisions")
```

Add to `test_publish_images_repairs_missing_sha_tags_without_overwriting_existing_ones`:

```python
assert "immutable SHA" not in content
assert "unable to determine SHA tag state for $image" in inspect_step
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
python -m pytest tests/test_ci_workflow.py -q
```

Expected: failures reference the current `immutable SHA` wording.

- [ ] **Step 3: Rename only workflow wording**

Apply these exact replacements:

```yaml
- name: Inspect SHA tags
```

```bash
echo "unable to determine SHA tag state for $image" >&2
```

```yaml
- name: Verify SHA image revisions
```

Do not change triggers, action SHAs, tags, annotations, build conditions, freshness checks, or promotion commands.

- [ ] **Step 4: Run tests**

```powershell
python -m pytest tests/test_ci_workflow.py -q
```

Expected: all workflow tests pass.

- [ ] **Step 5: Commit**

```powershell
git add .github/workflows/publish-images.yml tests/test_ci_workflow.py
git commit -m "ci: clarify SHA tag publication"
```

### Task 3: Update The Production Runbook

**Files:**

- Modify: `tests/test_container_deployment.py:2371-2403`
- Modify: `docs/deployment/container-production.md:14-32`
- Modify: `docs/deployment/container-production.md:78-86`
- Modify: `docs/deployment/container-production.md:140-148`

- [ ] **Step 1: Write failing runbook tests**

Replace the Enterprise-only ACR tests with:

```python
def test_container_runbook_documents_acr_edition_tradeoffs_and_sha_safety():
    content = read("docs/deployment/container-production.md")
    for required in [
        "ACR 企业版",
        "ACR 个人版",
        "crpi-your-instance.cn-beijing.personal.cr.aliyuncs.com",
        "registry.cn-beijing.aliyuncs.com",
        "无 SLA",
        "仅限开发测试",
        "40 位 Git SHA",
        "不会覆盖已存在的 SHA 标签",
        "拉取专用凭据",
        "docker login",
    ]:
        assert required in content
    assert "https://help.aliyun.com/zh/acr/product-overview/differences-between-personal-edition-instances-and-enterprise-edition-instances" in content
    assert "https://help.aliyun.com/zh/acr/user-guide/individual-edition-instance-independent-domain-name-capacity-limit" in content


def test_container_runbook_keeps_enterprise_immutability_and_operational_safety():
    content = read("docs/deployment/container-production.md")
    assert "https://help.aliyun.com/zh/acr/user-guide/turn-on-immutable-image-version" in content
    assert "企业版仓库" in content and "不可变" in content
    assert "个人版不提供仓库侧不可变保护" in content
    assert "Docker Compose 2.30" in content
    assert "最新 10" in content
    assert "异机" in content
    assert "df -h" in content
    assert "recover-interrupted.sh" in content
    assert "transaction" in content
    assert "down -v" not in content
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
python -m pytest tests/test_container_deployment.py::test_container_runbook_documents_acr_edition_tradeoffs_and_sha_safety tests/test_container_deployment.py::test_container_runbook_keeps_enterprise_immutability_and_operational_safety -q
```

Expected: both tests fail against the Enterprise-only runbook.

- [ ] **Step 3: Update runbook rules**

Document in Chinese that Enterprise remains recommended and should enable immutable versions; Personal is accepted as a transitional single-server choice but is officially development/test only and has no SLA. Document both Personal endpoint forms, no repository-side immutability, isolated credentials, no manual overwrite/deletion of 40-character SHA tags, and production never using `latest`.

Use this login example:

```bash
ACR_REGISTRY='crpi-your-instance.cn-beijing.personal.cr.aliyuncs.com'
read -rsp 'ACR pull password: ' ACR_PULL_PASSWORD && echo
printf '%s' "$ACR_PULL_PASSWORD" |
  docker login "$ACR_REGISTRY" --username 'YOUR_ECS_PULL_USERNAME' --password-stdin
unset ACR_PULL_PASSWORD
```

Change restore preflight wording from “企业版 ACR” to “受支持的北京 ACR 公网地址”.

- [ ] **Step 4: Run focused tests**

```powershell
python -m pytest tests/test_container_deployment.py::test_container_runbook_documents_acr_edition_tradeoffs_and_sha_safety tests/test_container_deployment.py::test_container_runbook_keeps_enterprise_immutability_and_operational_safety tests/test_container_deployment.py::test_deploy_script_accepts_supported_beijing_acr_public_endpoints tests/test_ci_workflow.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add docs/deployment/container-production.md tests/test_container_deployment.py
git commit -m "docs: support ACR personal deployment"
```

### Task 4: Full Verification

**Files:**

- Verify only; no expected source changes.

- [ ] **Step 1: Run deployment tests**

```powershell
python -m pytest tests/test_docker_support.py tests/test_container_deployment.py tests/test_ci_workflow.py tests/test_readme_links.py -q
```

Expected: all tests pass, with only the existing Windows `flock` skip allowed.

- [ ] **Step 2: Verify scripts and Compose**

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -n scripts/deploy.sh
& 'C:\Program Files\Git\bin\bash.exe' -n scripts/restore-data.sh
& 'C:\Program Files\Git\bin\bash.exe' -n scripts/recover-interrupted.sh
& 'C:\Program Files\Git\bin\bash.exe' -n scripts/production-preflight.sh
python -m py_compile scripts/inspect-restore-archive.py
$env:IMAGE_TAG='0123456789abcdef0123456789abcdef01234567'
docker compose --env-file deploy/.env.deploy.example -f compose.production.yml config --no-env-resolution
```

Expected: every command exits zero and Compose resolves both SHA-tagged images with the Personal example registry.

- [ ] **Step 3: Run complete application verification**

```powershell
python -m pytest -q
Push-Location frontend
npm test -- --run
npm run lint
npm run build
Pop-Location
```

Expected: backend and frontend tests, lint, and production build exit zero.

- [ ] **Step 4: Check formatting and state**

```powershell
python -m black --check tests/test_container_deployment.py tests/test_ci_workflow.py
git diff --check dba9d5e..HEAD
git status --short
```

Expected: formatting and diff checks pass, and the worktree is clean.
