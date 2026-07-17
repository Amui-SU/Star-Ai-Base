from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def active_dockerfile_lines(relative_path: str) -> list[str]:
    return [
        line.strip()
        for line in read(relative_path).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def active_dockerignore_rules(relative_path: str) -> set[str]:
    rules = set()
    for line in read(relative_path).splitlines():
        rule = line.strip()
        if rule and not rule.startswith(("#", "!")):
            rules.add(rule)
    return rules


def test_backend_image_defines_healthcheck_contract():
    lines = active_dockerfile_lines("Dockerfile.backend")
    healthcheck = (
        "HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \\"
    )
    command = (
        'CMD python -c "import urllib.request; '
        "urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()\""
    )

    healthcheck_index = lines.index(healthcheck)
    assert lines[healthcheck_index + 1] == command


def test_frontend_image_defines_api_url_and_healthcheck_contracts():
    lines = active_dockerfile_lines("frontend/Dockerfile")
    arg = "ARG NEXT_PUBLIC_API_URL=http://localhost:8000"
    env = "ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL"
    build = "RUN npm run build"
    healthcheck = (
        "HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\"
    )
    command = "CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/ || exit 1"

    assert lines.index(arg) < lines.index(build)
    assert lines.index(env) < lines.index(build)
    healthcheck_index = lines.index(healthcheck)
    assert lines[healthcheck_index + 1] == command


def test_root_dockerignore_excludes_runtime_and_production_files():
    rules = active_dockerignore_rules(".dockerignore")

    for entry in [".env*", "data/", "logs/", "deploy/.env.deploy"]:
        assert entry in rules


def test_frontend_dockerignore_excludes_local_build_and_environment_files():
    rules = active_dockerignore_rules("frontend/.dockerignore")

    for entry in [".env*", "node_modules/", ".next/", "out/"]:
        assert entry in rules


def production_compose() -> dict:
    return yaml.safe_load(read("compose.production.yml"))


def test_production_compose_uses_registry_images_without_build_contexts():
    compose = production_compose()
    services = compose["services"]
    expected_images = {
        "backend": (
            "${ACR_REGISTRY:?set ACR_REGISTRY}/"
            "${ACR_NAMESPACE:?set ACR_NAMESPACE}/"
            "zhiku-backend:${IMAGE_TAG:?set IMAGE_TAG}"
        ),
        "frontend": (
            "${ACR_REGISTRY:?set ACR_REGISTRY}/"
            "${ACR_NAMESPACE:?set ACR_NAMESPACE}/"
            "zhiku-frontend:${IMAGE_TAG:?set IMAGE_TAG}"
        ),
    }

    assert all("build" not in service for service in services.values())
    assert {name: service["image"] for name, service in services.items()} == (
        expected_images
    )
    assert read("compose.production.yml").count("${IMAGE_TAG:?set IMAGE_TAG}") == 2


def test_production_compose_exposes_only_loopback_ports_and_persists_backend_data():
    services = production_compose()["services"]

    assert services["backend"]["ports"] == ["127.0.0.1:8000:8000"]
    assert services["frontend"]["ports"] == ["127.0.0.1:3000:80"]
    assert services["backend"]["env_file"] == "./deploy/.env.production"
    assert services["backend"]["volumes"] == [
        "./data:/app/data",
        "./logs:/app/logs",
    ]


def test_production_compose_waits_for_backend_health_and_limits_logs():
    services = production_compose()["services"]
    expected_logging = {
        "driver": "json-file",
        "options": {"max-size": "10m", "max-file": "5"},
    }

    assert services["frontend"]["depends_on"] == {
        "backend": {"condition": "service_healthy"}
    }
    assert services["backend"]["logging"] == expected_logging
    assert services["frontend"]["logging"] == expected_logging


def test_production_compose_defines_runtime_and_healthcheck_contracts():
    compose = production_compose()
    services = compose["services"]

    assert compose["name"] == "zhiku-cloud"
    assert services["backend"]["restart"] == "unless-stopped"
    assert services["frontend"]["restart"] == "unless-stopped"
    assert services["backend"]["environment"] == {
        "APP_HOST": "0.0.0.0",
        "APP_PORT": 8000,
        "DATABASE_URL": "sqlite+aiosqlite:///./data/bilibili_rag.db",
        "CHROMA_PERSIST_DIRECTORY": "./data/chroma_db",
    }
    assert services["backend"]["healthcheck"] == {
        "test": [
            "CMD",
            "python",
            "-c",
            (
                "import urllib.request; "
                "urllib.request.urlopen('http://127.0.0.1:8000/health', "
                "timeout=3).read()"
            ),
        ],
        "interval": "30s",
        "timeout": "5s",
        "start_period": "20s",
        "retries": 3,
    }
    assert services["frontend"]["healthcheck"] == {
        "test": [
            "CMD-SHELL",
            "wget --no-verbose --tries=1 --spider http://127.0.0.1/ || exit 1",
        ],
        "interval": "30s",
        "timeout": "5s",
        "start_period": "10s",
        "retries": 3,
    }


def test_deploy_environment_example_contains_only_public_deployment_metadata():
    content = read("deploy/.env.deploy.example")

    assert content.splitlines() == [
        "ACR_REGISTRY=registry.cn-beijing.aliyuncs.com",
        "ACR_NAMESPACE=zhiku-cloud",
        "PUBLIC_BASE_URL=https://zhiku-cloud.cn",
    ]
    for forbidden in ["PASSWORD=", "SECRET=", "APP_ENCRYPTION_KEY="]:
        assert forbidden not in content


def test_deploy_script_validates_versions_and_never_deletes_runtime_state():
    content = read("scripts/deploy.sh")

    assert "set -Eeuo pipefail" in content
    assert "(( $# != 1 ))" in content
    assert "^[0-9a-f]{40}$" in content
    assert "compose()" in content
    assert "docker compose \\" in content
    assert "compose pull backend frontend" in content
    assert "compose up -d backend" in content
    assert "compose up -d frontend" in content
    assert "compose down" not in content
    assert "docker compose down -v" not in content
    assert "ACR_PASSWORD" not in content


def test_deploy_script_uses_rooted_files_and_public_deployment_metadata():
    content = read("scripts/deploy.sh")

    assert 'DEPLOY_ROOT="${ZHIKU_DEPLOY_ROOT:-/opt/zhiku-cloud}"' in content
    for path in [
        'COMPOSE_FILE="$DEPLOY_ROOT/compose.production.yml"',
        'DEPLOY_DIR="$DEPLOY_ROOT/deploy"',
        'DEPLOY_ENV="$DEPLOY_DIR/.env.deploy"',
        'APP_ENV="$DEPLOY_DIR/.env.production"',
        'DATA_DIR="$DEPLOY_ROOT/data"',
        'LOG_DIR="$DEPLOY_ROOT/logs"',
        'BACKUPS_DIR="$DEPLOY_ROOT/backups"',
        'CURRENT_FILE="$DEPLOY_DIR/current-version"',
        'PREVIOUS_FILE="$DEPLOY_DIR/previous-version"',
    ]:
        assert path in content

    assert "for command_name in docker curl tar; do" in content
    assert 'command -v "$command_name"' in content
    assert 'source "$DEPLOY_ENV"' in content
    assert 'source "$APP_ENV"' not in content
    for variable in ["ACR_REGISTRY", "ACR_NAMESPACE", "PUBLIC_BASE_URL"]:
        assert f"${{{variable}:?" in content
    assert "export ACR_REGISTRY ACR_NAMESPACE IMAGE_TAG" in content
    assert 'mkdir -p "$DEPLOY_DIR" "$DATA_DIR" "$LOG_DIR" "$BACKUPS_DIR"' in content


def test_deploy_script_backs_up_before_rollout_and_tracks_successful_versions():
    content = read("scripts/deploy.sh")

    pull = content.index("compose pull backend frontend")
    stop = content.index("compose stop backend")
    backup = content.index('tar -C "$DATA_DIR" -czf "$BACKUP_DIR/data.tar.gz" .')
    backend = content.index("compose up -d backend", backup)
    frontend = content.index("compose up -d frontend", backend)

    assert pull < stop < backup < backend < frontend
    assert "date -u +%Y%m%dT%H%M%SZ" in content
    assert '"$BACKUP_DIR/previous-image-tag"' in content
    assert 'printf \'%s\\n\' "$PREVIOUS_TAG" > "$PREVIOUS_FILE"' in content
    assert 'printf \'%s\\n\' "$TARGET_TAG" > "$CURRENT_FILE.tmp"' in content
    assert 'mv "$CURRENT_FILE.tmp" "$CURRENT_FILE"' in content


def test_deploy_script_has_image_only_rollback_and_all_health_checks():
    content = read("scripts/deploy.sh")
    rollback = content[content.index("rollback()") : content.index("on_error()")]

    assert "DEPLOY_STARTED=false" in content
    assert "trap on_error ERR" in content
    assert "rollback ||" in content
    assert "tar " not in rollback
    assert "compose up -d backend" in rollback
    assert "compose up -d frontend" in rollback
    assert 'wait_http "http://127.0.0.1:8000/health"' in rollback
    assert 'wait_http "http://127.0.0.1:3000/"' in rollback
    assert 'wait_http "${PUBLIC_BASE_URL%/}/health"' in rollback

    for url in [
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:3000/",
        "${PUBLIC_BASE_URL%/}/",
        "${PUBLIC_BASE_URL%/}/health",
    ]:
        assert f'wait_http "{url}"' in content
    assert "curl --fail --silent --show-error --max-time 5" in content
