import configparser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_publish_workflow() -> str:
    workflow = PROJECT_ROOT / ".github" / "workflows" / "publish-images.yml"

    assert workflow.exists(), "Publish Images workflow must exist"
    return workflow.read_text(encoding="utf-8")


def test_github_actions_ci_runs_backend_and_frontend_quality_gates():
    project_root = Path(__file__).resolve().parents[1]
    workflow = project_root / ".github" / "workflows" / "ci.yml"

    assert workflow.exists()
    content = workflow.read_text(encoding="utf-8")
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
    ]:
        assert required in content

    assert (
        "github.event.workflow_run.conclusion == 'success' && "
        "github.event.workflow_run.event == 'push'"
    ) in normalized


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
        "docker/login-action@c99871dec2022cc055c062a10cc1a1310835ceb4",
    ]:
        assert required in content


def test_publish_images_builds_sha_and_latest_backend_and_frontend_images():
    content = read_publish_workflow()

    for required in [
        "file: Dockerfile.backend",
        "file: frontend/Dockerfile",
        "NEXT_PUBLIC_API_URL=https://zhiku-cloud.cn",
        "${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-backend:${{ env.IMAGE_TAG }}",
        "${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-backend:latest",
        "${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-frontend:${{ env.IMAGE_TAG }}",
        "${{ env.ACR_REGISTRY }}/${{ env.ACR_NAMESPACE }}/zhiku-frontend:latest",
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
    assert "ssh" not in content.lower()
    assert "deploy" not in content.lower()
