import configparser
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_publish_workflow() -> str:
    workflow = PROJECT_ROOT / ".github" / "workflows" / "publish-images.yml"

    assert workflow.exists(), "Publish Images workflow must exist"
    return workflow.read_text(encoding="utf-8")


def read_ci_workflow() -> str:
    workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"

    assert workflow.exists(), "CI workflow must exist"
    return workflow.read_text(encoding="utf-8")


def test_github_actions_ci_runs_backend_and_frontend_quality_gates():
    content = read_ci_workflow()
    for required in [
        "python -m pytest -q",
        "npm ci",
        "npm run lint",
        "npm test",
        "npm run build",
    ]:
        assert required in content


def test_pytest_asyncio_fixture_loop_scope_is_explicit():
    config = configparser.ConfigParser()
    read_files = config.read(Path(__file__).resolve().parents[1] / "pytest.ini")

    assert read_files
    assert config.get("pytest", "asyncio_default_fixture_loop_scope") == "function"


def test_pytest_warning_filters_only_known_upstream_multipart_warning():
    config = configparser.ConfigParser()
    config.read(Path(__file__).resolve().parents[1] / "pytest.ini")

    filters = "\n".join(
        value
        for key, value in config.items("pytest")
        if key.startswith("filterwarnings")
    )

    assert "Please use `import python_multipart` instead." in filters
    assert "starlette.formparsers" in filters


def test_publish_images_runs_only_after_successful_main_push_ci():
    content = read_publish_workflow()
    normalized = " ".join(content.split())

    for required in [
        "name: Publish Images",
        "workflow_run:",
        'workflows: ["CI"]',
        "types: [completed]",
        "branches: [main]",
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'push'",
        "permissions:",
        "contents: read",
        "concurrency:",
        "group: publish-images",
        "cancel-in-progress: false",
        "queue: max",
        "timeout-minutes:",
    ]:
        assert required in content

    assert (
        "github.event.workflow_run.conclusion == 'success' && "
        "github.event.workflow_run.event == 'push'"
    ) in normalized
    assert re.search(r"timeout-minutes:\s+[1-9][0-9]*", content)


def test_publish_images_uses_tested_commit_and_acr_configuration():
    content = read_publish_workflow()

    for required in [
        "ref: ${{ github.event.workflow_run.head_sha }}",
        "IMAGE_TAG: ${{ github.event.workflow_run.head_sha }}",
        "ACR_REGISTRY: ${{ secrets.ACR_REGISTRY }}",
        "ACR_USERNAME: ${{ secrets.ACR_USERNAME }}",
        "ACR_PASSWORD: ${{ secrets.ACR_PASSWORD }}",
        "ACR_NAMESPACE: ${{ vars.ACR_NAMESPACE }}",
        "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",
        "docker/setup-buildx-action@bb05f3f5519dd87d3ba754cc423b652a5edd6d2c",
        "docker/login-action@c99871dec2022cc055c062a10cc1a1310835ceb4",
    ]:
        assert required in content

    assert content.index("docker/setup-buildx-action@") < content.index(
        "docker/build-push-action@"
    )


def test_publish_images_repairs_missing_sha_tags_without_overwriting_existing_ones():
    content = read_publish_workflow()

    inspect_index = content.index("- name: Inspect immutable SHA tags")
    backend_build_index = content.index("- name: Build and publish backend image")
    frontend_build_index = content.index("- name: Build and publish frontend image")
    inspect_step = content[inspect_index:backend_build_index]

    assert "id: sha_tags" in inspect_step
    assert "docker buildx imagetools inspect" in inspect_step
    assert 'backend_state="$(inspect_tag "$BACKEND_IMAGE")"' in inspect_step
    assert 'frontend_state="$(inspect_tag "$FRONTEND_IMAGE")"' in inspect_step
    assert "manifest unknown|not found|no such manifest" in inspect_step
    assert 'echo "backend_build=$(state_to_build "$backend_state")"' in inspect_step
    assert 'echo "frontend_build=$(state_to_build "$frontend_state")"' in inspect_step
    assert "only one immutable SHA tag exists" not in inspect_step

    backend_header = content[backend_build_index:frontend_build_index].split(
        "with:", 1
    )[0]
    frontend_header = content[frontend_build_index:].split("with:", 1)[0]
    assert "if: steps.sha_tags.outputs.backend_build == 'true'" in backend_header
    assert "if: steps.sha_tags.outputs.frontend_build == 'true'" in frontend_header


def test_publish_images_annotates_and_verifies_both_sha_manifests_before_freshness():
    content = read_publish_workflow()
    backend_build_index = content.index("- name: Build and publish backend image")
    frontend_build_index = content.index("- name: Build and publish frontend image")
    verify_index = content.index("- name: Verify immutable SHA image revisions")
    freshness_index = content.index("- name: Verify tested commit is still current")

    backend_build = content[backend_build_index:frontend_build_index]
    frontend_build = content[frontend_build_index:verify_index]
    annotation = "index:org.opencontainers.image.revision=${{ env.IMAGE_TAG }}"
    assert annotation in backend_build
    assert annotation in frontend_build

    verify_step = content[verify_index:freshness_index]
    assert "command -v jq" in verify_step
    assert verify_step.count("docker buildx imagetools inspect --raw") == 1
    assert 'verify_revision "$BACKEND_IMAGE"' in verify_step
    assert 'verify_revision "$FRONTEND_IMAGE"' in verify_step
    assert "org.opencontainers.image.revision" in verify_step
    assert 'jq -e --arg revision "$IMAGE_TAG"' in verify_step
    assert verify_index < freshness_index


def test_publish_images_builds_sha_only_then_promotes_both_images_when_current():
    content = read_publish_workflow()

    for required in [
        "file: Dockerfile.backend",
        "file: frontend/Dockerfile",
        "NEXT_PUBLIC_API_URL=https://zhiku-cloud.cn",
        "${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-backend:${{ env.IMAGE_TAG }}",
        "${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-frontend:${{ env.IMAGE_TAG }}",
        "scope=backend",
        "scope=frontend",
    ]:
        assert required in content

    assert (
        content.count(
            "docker/build-push-action@53b7df96c91f9c12dcc8a07bcb9ccacbed38856a"
        )
        == 2
    )
    assert content.count("push: true") == 2

    backend_build = content.split("- name: Build and publish backend image", 1)[
        1
    ].split("- name: Build and publish frontend image", 1)[0]
    frontend_build = content.split("- name: Build and publish frontend image", 1)[
        1
    ].split("- name: Verify immutable SHA image revisions", 1)[0]
    assert ":latest" not in backend_build
    assert ":latest" not in frontend_build

    freshness_index = content.index("- name: Verify tested commit is still current")
    remote_head_index = content.index("refs/remotes/origin/main")
    backend_promotion_index = content.index(
        "docker buildx imagetools create",
        remote_head_index,
    )
    frontend_promotion_index = content.index(
        "docker buildx imagetools create",
        backend_promotion_index + 1,
    )

    revision_index = content.index("- name: Verify immutable SHA image revisions")
    assert content.index("- name: Build and publish frontend image") < revision_index
    assert revision_index < freshness_index
    assert freshness_index < remote_head_index < backend_promotion_index
    assert "id: freshness" in content[freshness_index:backend_promotion_index]
    assert '[[ "$remote_main_sha" != "$IMAGE_TAG" ]]' in content
    stale_branch = content.split(
        'if [[ "$remote_main_sha" != "$IMAGE_TAG" ]]; then', 1
    )[1].split("fi", 1)[0]
    assert 'echo "promote=false" >> "$GITHUB_OUTPUT"' in stale_branch
    assert "exit 0" in stale_branch
    assert (
        'echo "promote=true" >> "$GITHUB_OUTPUT"'
        in content[remote_head_index:backend_promotion_index]
    )
    assert backend_promotion_index < frontend_promotion_index
    assert content.count("docker buildx imagetools create") == 2
    promotion_step = content.split("- name: Promote tested images to latest", 1)[1]
    promotion_header = promotion_step.split("run: |", 1)[0]
    assert "if: steps.freshness.outputs.promote == 'true'" in promotion_header
    assert (
        "BACKEND_IMAGE: ${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-backend"
        in promotion_step
    )
    assert (
        "FRONTEND_IMAGE: ${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-frontend"
        in promotion_step
    )
    promotion_script = promotion_step.split("run: |", 1)[1]
    assert "${{" not in promotion_script
    assert '--tag "${BACKEND_IMAGE}:latest"' in promotion_script
    assert '"${BACKEND_IMAGE}:${IMAGE_TAG}"' in promotion_script
    assert '--tag "${FRONTEND_IMAGE}:latest"' in promotion_script
    assert '"${FRONTEND_IMAGE}:${IMAGE_TAG}"' in promotion_script
    assert "ssh" not in content.lower()
    assert "deploy" not in content.lower()


def test_workflows_pin_all_actions_and_use_read_only_contents_permission():
    workflows = {
        "ci.yml": read_ci_workflow(),
        "publish-images.yml": read_publish_workflow(),
    }

    for name, content in workflows.items():
        header = content.split("jobs:", 1)[0]
        assert "permissions:\n  contents: read" in header, name

        refs = re.findall(r"^\s*(?:-\s+)?uses:\s+\S+@([^\s#]+)", content, re.MULTILINE)
        assert refs, name
        assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in refs), name

    ci_content = workflows["ci.yml"]
    assert (
        ci_content.count("actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0")
        == 2
    )
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" in ci_content
    assert "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020" in ci_content
