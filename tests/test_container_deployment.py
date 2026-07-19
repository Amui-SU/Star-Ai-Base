import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = PROJECT_ROOT / "scripts" / "deploy.sh"
RESTORE_SCRIPT = PROJECT_ROOT / "scripts" / "restore-data.sh"
RECOVER_SCRIPT = PROJECT_ROOT / "scripts" / "recover-interrupted.sh"
TARGET_TAG = "1" * 40
PREVIOUS_TAG = "2" * 40
VALID_FERNET_KEY = "A" * 43 + "="
ENTERPRISE_ACR = "test-instance-registry.cn-beijing.cr.aliyuncs.com"


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_shell_scripts_keep_linux_line_endings():
    assert "*.sh text eol=lf" in read(".gitattributes")


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


def test_frontend_runtime_uses_pinned_supported_nginx_image():
    lines = active_dockerfile_lines("frontend/Dockerfile")

    assert (
        "FROM nginx:1.30.4-alpine@"
        "sha256:97d490c12ba55b4946b01546d1c3ed324e8d41ab1c9fcb2a616aa470620e5b46"
        in lines
    )


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
    assert services["backend"]["env_file"] == [
        {"path": "./deploy/.env.production", "format": "raw"}
    ]
    assert services["backend"]["volumes"] == [
        "./data:/app/data",
        "./logs:/app/logs",
    ]
    assert services["backend"]["environment"]["FORWARDED_ALLOW_IPS"] == "*"


def test_production_compose_preserves_dollar_sign_secrets_by_contract():
    backend = production_compose()["services"]["backend"]

    assert backend["env_file"] == [
        {"path": "./deploy/.env.production", "format": "raw"}
    ]
    assert "format: raw" in read("compose.production.yml")


def test_compose_config_preserves_literal_dollar_sign_secrets(tmp_path):
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker Compose CLI is unavailable")
    version = subprocess.run(
        [docker, "compose", "version", "--short"],
        capture_output=True,
        text=True,
        check=False,
    )
    if version.returncode != 0:
        pytest.skip("Docker Compose CLI is unavailable")

    root = tmp_path / "compose-contract"
    deploy_dir = root / "deploy"
    deploy_dir.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "compose.production.yml", root)
    (deploy_dir / ".env.deploy").write_text(
        f"ACR_REGISTRY={ENTERPRISE_ACR}\nACR_NAMESPACE=zhiku\n",
        encoding="utf-8",
    )
    secret = "smtp-$literal-$$-value"
    (deploy_dir / ".env.production").write_text(
        f"SMTP_PASSWORD={secret}\nAPI_SECRET=$provider$key\n", encoding="utf-8"
    )
    environment = os.environ.copy()
    environment["IMAGE_TAG"] = TARGET_TAG
    result = subprocess.run(
        [
            docker,
            "compose",
            "--project-directory",
            str(root),
            "--env-file",
            str(deploy_dir / ".env.deploy"),
            "-f",
            str(root / "compose.production.yml"),
            "config",
            "--format",
            "json",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    backend_env = json.loads(result.stdout)["services"]["backend"]["environment"]
    # Compose config escapes literal dollars as $$ in its serialized model; the
    # container receives the original single-dollar values.
    assert backend_env["SMTP_PASSWORD"] == secret.replace("$", "$$")
    assert backend_env["API_SECRET"] == "$$provider$$key"


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
        "FORWARDED_ALLOW_IPS": "*",
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
        "ACR_REGISTRY=your-instance-registry.cn-beijing.cr.aliyuncs.com",
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
    assert "compose up -d --pull never backend" in content
    assert "compose up -d --pull never frontend" in content
    assert "compose down" not in content
    assert "docker compose down -v" not in content
    assert "ACR_PASSWORD" not in content


def test_deploy_script_uses_rooted_files_and_public_deployment_metadata():
    content = read("scripts/deploy.sh")
    preflight = read("scripts/production-preflight.sh")

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

    for command_name in ["docker", "curl", "tar", "flock", "mktemp", "du", "df"]:
        assert command_name in content
    assert 'command -v "$command_name"' in content
    assert 'source "$DEPLOY_ENV"' not in content
    assert 'source "$APP_ENV"' not in content
    for variable in ["ACR_REGISTRY", "ACR_NAMESPACE", "PUBLIC_BASE_URL"]:
        assert f"{variable})" in preflight
    assert "readonly ACR_REGISTRY ACR_NAMESPACE PUBLIC_BASE_URL" in content
    assert "--project-name zhiku-cloud" in content
    assert "umask 077" in content
    assert 'mkdir -p "$DEPLOY_DIR" "$DATA_DIR" "$LOG_DIR" "$BACKUPS_DIR"' in content


def test_deploy_script_enforces_disk_compose_cookie_and_transaction_preflights():
    content = read("scripts/deploy.sh")
    preflight = read("scripts/production-preflight.sh")

    assert "ZHIKU_DEPLOY_DISK_RESERVE_BYTES:-2147483648" in content
    assert 'du -sk -- "$DATA_DIR"' in content
    assert 'df -Pk -- "$BACKUPS_DIR"' in content
    assert "Docker Compose >= 2.30" in content
    assert 'source "$PRODUCTION_PREFLIGHT"' in content
    assert 'production_preflight "$DEPLOY_ENV" "$APP_ENV"' in content
    assert "${SESSION_COOKIE_SECURE_VALUE,,}" in preflight
    assert "== true" in preflight
    assert 'TRANSACTION_FILE="$DEPLOY_DIR/transaction"' in content
    assert "recover-interrupted.sh" in content
    pull_index = content.index("compose pull backend frontend")
    disk_index = content.index('du -sk -- "$DATA_DIR"')
    backup_dir_index = content.index('mktemp -d "$BACKUPS_DIR/')
    stop_index = content.index("compose stop backend", pull_index)
    assert pull_index < disk_index < backup_dir_index < stop_index
    assert "backup_dir=$BACKUP_DIR" in content


def test_deploy_script_requires_beijing_enterprise_acr_endpoint():
    content = read("scripts/production-preflight.sh")

    assert "cn-beijing\\.cr\\.aliyuncs\\.com" in content
    assert "your-instance-registry.cn-beijing.cr.aliyuncs.com" in content
    assert "Enterprise Edition" in content


def test_restore_script_enforces_20_gib_limit_disk_budget_and_transaction_marker():
    content = read("scripts/restore-data.sh")

    assert "ZHIKU_RESTORE_MAX_BYTES:-21474836480" in content
    assert "ZHIKU_RESTORE_DISK_RESERVE_BYTES:-2147483648" in content
    assert 'df -Pk -- "$DEPLOY_ROOT"' in content
    assert 'TRANSACTION_FILE="$DEPLOY_DIR/transaction"' in content
    assert "recover-interrupted.sh" in content
    assert 'source "$PRODUCTION_PREFLIGHT"' in content
    assert 'production_preflight "$DEPLOY_ENV" "$APP_ENV"' in content
    assert 'rm -f -- "$BACKUP_DIR/data.tar.gz.partial"' in read("scripts/deploy.sh")


def test_deploy_and_restore_share_one_read_only_production_preflight():
    helper = read("scripts/production-preflight.sh")

    assert "source " not in helper
    assert "eval " not in helper
    assert "docker " not in helper
    assert "production_preflight()" in helper
    for script in ["scripts/deploy.sh", "scripts/restore-data.sh"]:
        content = read(script)
        assert 'PRODUCTION_PREFLIGHT="$SCRIPT_DIR/production-preflight.sh"' in content
        assert 'source "$PRODUCTION_PREFLIGHT"' in content
        assert content.count('production_preflight "$DEPLOY_ENV" "$APP_ENV"') == 1


def test_recovery_script_has_strict_transaction_contract():
    content = read("scripts/recover-interrupted.sh")

    assert "set -Eeuo pipefail" in content
    assert 'TRANSACTION_FILE="$DEPLOY_DIR/transaction"' in content
    assert 'source "$TRANSACTION_FILE"' not in content
    assert "eval " not in content
    assert "flock -n 9" in content
    assert "operation=deploy" in content
    assert "operation=restore" in content
    assert "--pull never backend" in content
    assert "--pull never frontend" in content
    assert "backend left stopped" in content
    assert "backup_dir" in content
    assert "data.tar.gz.partial" in content


def test_deploy_script_backs_up_before_rollout_and_tracks_successful_versions():
    content = read("scripts/deploy.sh")

    assert 'tar -C "$DATA_DIR" -czf "$PARTIAL_ARCHIVE" .' in content
    assert 'mv -- "$PARTIAL_ARCHIVE" "$BACKUP_DIR/data.tar.gz"' in content
    assert "date -u +%Y%m%dT%H%M%SZ" in content
    assert 'mktemp -d "$BACKUPS_DIR/' in content
    assert '"$BACKUP_DIR/previous-image-tag"' in content
    assert 'mktemp "${destination}.tmp.XXXXXX"' in content
    assert 'atomic_write "$PREVIOUS_TAG" "$PREVIOUS_FILE"' in content
    assert 'atomic_write "$TARGET_TAG" "$CURRENT_FILE"' in content


def test_deploy_script_has_image_only_rollback_and_all_health_checks():
    content = read("scripts/deploy.sh")
    rollback = content[content.index("rollback()") : content.index("on_error()")]

    assert "DEPLOY_STARTED=false" in content
    assert "trap on_error ERR" in content
    assert "if ! recover_images; then" in content
    assert "tar " not in rollback
    assert "compose up -d --pull never backend" in rollback
    assert "compose up -d --pull never frontend" in rollback
    assert 'wait_http "http://127.0.0.1:8000/health"' in rollback
    assert 'wait_http "http://127.0.0.1:3000/"' in rollback
    assert 'wait_http "${PUBLIC_BASE_URL%/}/"' in rollback
    assert 'wait_http "${PUBLIC_BASE_URL%/}/health"' in rollback
    assert "trap 'on_signal 130' INT" in content
    assert "trap 'on_signal 143' TERM" in content
    assert "trap 'on_signal 129' HUP" in content

    for url in [
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:3000/",
        "${PUBLIC_BASE_URL%/}/",
        "${PUBLIC_BASE_URL%/}/health",
    ]:
        assert f'wait_http "{url}"' in content
    for option in ["--fail", "--silent", "--show-error", "--max-time 5"]:
        assert option in content
    assert "--max-redirs 0" in content


def write_fake_tool(bin_dir: Path, name: str, content: str) -> None:
    path = bin_dir / name
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def bash_executable() -> str:
    git_bash = Path("C:/Program Files/Git/bin/bash.exe")
    if git_bash.exists():
        return str(git_bash)

    bash = shutil.which("bash")
    assert bash is not None, "bash is required for deployment behavior tests"
    return bash


def bash_path(path: Path) -> str:
    absolute = path.resolve().as_posix()
    if os.name == "nt":
        drive, remainder = absolute.split(":", 1)
        return f"/{drive.lower()}{remainder}"
    return absolute


def valid_production_environment() -> str:
    return (
        "DEBUG=false\n"
        "SESSION_COOKIE_SECURE=true\n"
        "ADMIN_EMAILS=admin@zhiku-cloud.cn\n"
        f"APP_ENCRYPTION_KEY={VALID_FERNET_KEY}\n"
        "SMTP_HOST=smtp.example.net\n"
        "SMTP_USER=mailer@zhiku-cloud.cn\n"
        "SMTP_PASSWORD=password=$literal=with=equals\n"
        "SMTP_FROM=mailer@zhiku-cloud.cn\n"
        "OPTIONAL_PROVIDER_VALUE=kept=with=equals\n"
    )


def deployment_fixture(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "deploy-root"
    deploy_dir = root / "deploy"
    data_dir = root / "data"
    bin_dir = tmp_path / "bin"
    deploy_dir.mkdir(parents=True)
    data_dir.mkdir()
    bin_dir.mkdir()

    (root / "compose.production.yml").write_text("services: {}\n", encoding="utf-8")
    (deploy_dir / ".env.deploy").write_text(
        f"ACR_REGISTRY={ENTERPRISE_ACR}\n"
        "ACR_NAMESPACE=zhiku\n"
        "PUBLIC_BASE_URL=https://public.example.test\n",
        encoding="utf-8",
    )
    (deploy_dir / ".env.production").write_text(
        valid_production_environment(), encoding="utf-8"
    )
    (data_dir / "database.sqlite").write_text("data", encoding="utf-8")

    marker = tmp_path / "env-command-ran"
    docker_log = tmp_path / "docker.log"
    curl_log = tmp_path / "curl.log"
    tar_log = tmp_path / "tar.log"

    write_fake_tool(
        bin_dir,
        "docker",
        """#!/usr/bin/env bash
set -u
if [[ "$*" == "compose version --short" ]]; then
  printf '%s\n' "${FAKE_COMPOSE_VERSION:-2.30.0}"
  exit 0
fi
[[ "${1:-}" == compose ]] || exit 90
shift
project_name=""
while (( $# > 0 )); do
  case "$1" in
    --project-name) project_name="$2"; shift 2 ;;
    --project-directory|--env-file|-f) shift 2 ;;
    *) break ;;
  esac
done
[[ "$project_name" == zhiku-cloud ]] || exit 92
command_line="$*"
printf '%s|%s\n' "${IMAGE_TAG:-unset}" "$command_line" >> "$FAKE_DOCKER_LOG"
case "$command_line" in
  "ps --all --services backend frontend")
    printf '%s\n' "${FAKE_EXISTING_SERVICES:-}"
    ;;
  "pull backend frontend")
    if [[ -n "${FAKE_PULL_MARKER:-}" ]]; then
      : > "$FAKE_PULL_MARKER"
    fi
    exit "${FAKE_PULL_EXIT:-0}"
    ;;
  "stop backend")
    exit "${FAKE_STOP_EXIT:-0}"
    ;;
  "ps --all --format {{.State}} backend")
    printf '%s\n' "${FAKE_POST_STOP_STATES:-}"
    ;;
  "up -d --pull never backend"|"up -d --pull never frontend"|"stop frontend")
    ;;
  *)
    exit 93
    ;;
esac
""",
    )
    write_fake_tool(
        bin_dir,
        "curl",
        """#!/usr/bin/env bash
set -u
url="${!#}"
printf '%s|%s\n' "${IMAGE_TAG:-unset}" "$url" >> "$FAKE_CURL_LOG"
if [[ -n "${FAKE_CURL_FAIL_TAG:-}" && "${IMAGE_TAG:-}" == "$FAKE_CURL_FAIL_TAG" ]]; then
  exit 22
fi
status=200
body=ok
if [[ "$url" == */health ]]; then
  body='{"status":"healthy"}'
fi
if [[ "$url" == https://public.example.test/health && "${IMAGE_TAG:-}" == "${FAKE_STRICT_TAG:-}" ]]; then
  status="${FAKE_PUBLIC_HEALTH_STATUS:-$status}"
  body="${FAKE_PUBLIC_HEALTH_BODY:-$body}"
fi
printf '%s\n%s' "$body" "$status"
""",
    )
    write_fake_tool(
        bin_dir,
        "tar",
        """#!/usr/bin/env bash
set -u
printf '%s\n' "$*" >> "$FAKE_TAR_LOG"
archive=""
while (( $# > 0 )); do
  if [[ "$1" == -czf ]]; then
    archive="$2"
    break
  fi
  shift
done
[[ -n "$archive" ]] || exit 91
if [[ -n "${FAKE_TAR_SIGNAL:-}" ]]; then
  kill -s "$FAKE_TAR_SIGNAL" "$PPID"
  sleep 1
fi
printf 'fake archive\n' > "$archive"
if [[ -n "${FAKE_TAR_EXIT:-}" ]]; then
  exit "$FAKE_TAR_EXIT"
fi
""",
    )
    write_fake_tool(
        bin_dir,
        "flock",
        """#!/usr/bin/env bash
if [[ "${FAKE_LOCK_HELD:-0}" == 1 ]]; then
  exit 1
fi
""",
    )
    write_fake_tool(
        bin_dir,
        "mktemp",
        """#!/usr/bin/env bash
if [[ "${1:-}" == -d && -n "${FAKE_MKTEMP_DIR_EXIT:-}" ]]; then
  exit "$FAKE_MKTEMP_DIR_EXIT"
fi
exec /usr/bin/mktemp "$@"
""",
    )
    write_fake_tool(
        bin_dir,
        "du",
        """#!/usr/bin/env bash
printf '%s\t%s\n' "${FAKE_DATA_KIB:-4}" "${!#}"
""",
    )
    write_fake_tool(
        bin_dir,
        "df",
        """#!/usr/bin/env bash
printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n'
available="${FAKE_AVAILABLE_KIB:-4194304}"
if [[ -n "${FAKE_PULL_MARKER:-}" && -e "$FAKE_PULL_MARKER" ]]; then
  available="${FAKE_AFTER_PULL_AVAILABLE_KIB:-$available}"
fi
printf 'fake 8388608 0 %s 0%% /\n' "$available"
""",
    )
    write_fake_tool(
        bin_dir,
        "mv",
        """#!/usr/bin/env bash
/usr/bin/mv "$@" || exit $?
destination="${!#}"
if [[ -n "${FAKE_SIGNAL_ON_CURRENT:-}" && "$destination" == */current-version && ! -e "$FAKE_SIGNAL_MARKER" ]]; then
  : > "$FAKE_SIGNAL_MARKER"
  kill -s "$FAKE_SIGNAL_ON_CURRENT" "$PPID"
  sleep 1
fi
""",
    )
    write_fake_tool(bin_dir, "sleep", "#!/usr/bin/env bash\nexit 0\n")

    env = os.environ.copy()
    env.update(
        {
            "ZHIKU_DEPLOY_ROOT": root.as_posix(),
            "FAKE_DOCKER_LOG": bash_path(docker_log),
            "FAKE_CURL_LOG": bash_path(curl_log),
            "FAKE_TAR_LOG": bash_path(tar_log),
            "FAKE_SIGNAL_MARKER": bash_path(tmp_path / "signal.marker"),
            "FAKE_PULL_MARKER": bash_path(tmp_path / "pull.marker"),
            "ZHIKU_DEPLOY_HTTP_ATTEMPTS": "2",
            "ZHIKU_DEPLOY_HTTP_DELAY_SECONDS": "0",
        }
    )
    env["ZHIKU_DEPLOY_ROOT"] = bash_path(root)
    return {
        "root": root,
        "deploy_dir": deploy_dir,
        "bin_dir": bin_dir,
        "marker": marker,
        "env": env,
        "docker_log": docker_log,
        "curl_log": curl_log,
        "tar_log": tar_log,
    }


def run_deploy(
    fixture: dict[str, object], **env_updates: str
) -> subprocess.CompletedProcess:
    env = dict(fixture["env"])
    env.update(env_updates)
    return subprocess.run(
        [
            bash_executable(),
            "-c",
            'PATH="$1:$PATH"; export PATH; exec bash "$2" "$3"',
            "deploy-test",
            bash_path(Path(fixture["bin_dir"])),
            bash_path(DEPLOY_SCRIPT),
            TARGET_TAG,
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )


def log_lines(path: object) -> list[str]:
    log_path = Path(path)
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8").splitlines()


def test_deploy_script_allows_fresh_first_deployment(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "previous-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    result = run_deploy(fixture)

    assert result.returncode == 0, result.stderr
    commands = log_lines(fixture["docker_log"])
    assert f"{TARGET_TAG}|pull backend frontend" in commands
    assert f"{TARGET_TAG}|stop backend" in commands
    assert f"{TARGET_TAG}|up -d --pull never backend" in commands
    assert f"{TARGET_TAG}|up -d --pull never frontend" in commands
    assert (deploy_dir / "current-version").read_text().strip() == TARGET_TAG
    assert not (deploy_dir / "previous-version").exists()


def test_deploy_script_rejects_unknown_existing_backend_before_mutation(tmp_path):
    fixture = deployment_fixture(tmp_path)

    result = run_deploy(fixture, FAKE_EXISTING_SERVICES="backend")

    assert result.returncode != 0
    assert "valid current SHA" in result.stderr
    commands = log_lines(fixture["docker_log"])
    assert commands == [f"{TARGET_TAG}|ps --all --services backend frontend"]
    assert log_lines(fixture["tar_log"]) == []


def test_deploy_script_pull_failure_does_not_mutate_runtime(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend",
        FAKE_PULL_EXIT="17",
    )

    assert result.returncode == 17
    commands = log_lines(fixture["docker_log"])
    assert f"{TARGET_TAG}|stop backend" not in commands
    assert not any("|up -d " in command for command in commands)
    assert log_lines(fixture["tar_log"]) == []


def test_deploy_script_stop_failure_attempts_image_rollback(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend",
        FAKE_STOP_EXIT="18",
    )

    assert result.returncode == 18
    commands = log_lines(fixture["docker_log"])
    assert f"{TARGET_TAG}|stop backend" in commands
    assert f"{PREVIOUS_TAG}|up -d --pull never backend" in commands
    assert f"{PREVIOUS_TAG}|up -d --pull never frontend" in commands
    assert log_lines(fixture["tar_log"]) == []


def test_deploy_script_restarting_backend_after_stop_triggers_rollback(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend",
        FAKE_POST_STOP_STATES="restarting",
    )

    assert result.returncode != 0
    assert "backend did not stop" in result.stderr
    assert f"{PREVIOUS_TAG}|up -d --pull never backend" in log_lines(
        fixture["docker_log"]
    )
    assert log_lines(fixture["tar_log"]) == []


def test_deploy_script_health_failure_completes_public_rollback_checks(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend",
        FAKE_POST_STOP_STATES="exited",
        FAKE_CURL_FAIL_TAG=TARGET_TAG,
    )

    assert result.returncode != 0
    commands = log_lines(fixture["docker_log"])
    assert f"{TARGET_TAG}|up -d --pull never backend" in commands
    assert f"{PREVIOUS_TAG}|up -d --pull never backend" in commands
    curl_calls = log_lines(fixture["curl_log"])
    assert f"{PREVIOUS_TAG}|https://public.example.test/" in curl_calls
    assert f"{PREVIOUS_TAG}|https://public.example.test/health" in curl_calls


def test_deploy_script_success_tracks_versions_and_complete_backup(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend",
        FAKE_POST_STOP_STATES="exited",
    )

    assert result.returncode == 0, result.stderr
    commands = log_lines(fixture["docker_log"])
    previous_pull = commands.index(f"{PREVIOUS_TAG}|pull backend frontend")
    stop = commands.index(f"{TARGET_TAG}|stop backend")
    assert previous_pull < stop
    assert (deploy_dir / "current-version").read_text().strip() == TARGET_TAG
    assert (deploy_dir / "previous-version").read_text().strip() == PREVIOUS_TAG
    assert list(deploy_dir.glob("*.tmp.*")) == []
    backup_dirs = list((Path(fixture["root"]) / "backups").iterdir())
    assert len(backup_dirs) == 1
    assert (backup_dirs[0] / "data.tar.gz").is_file()
    assert (backup_dirs[0] / "previous-image-tag").read_text().strip() == PREVIOUS_TAG


def test_deploy_script_fails_clearly_when_deployment_lock_is_held(tmp_path):
    fixture = deployment_fixture(tmp_path)

    result = run_deploy(fixture, FAKE_LOCK_HELD="1")

    assert result.returncode != 0
    assert "another deployment is already in progress" in result.stderr
    assert log_lines(fixture["docker_log"]) == []


def test_deploy_script_rejects_env_command_and_unknown_project_override(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    marker = Path(fixture["marker"])
    (deploy_dir / ".env.deploy").write_text(
        f"ACR_REGISTRY={ENTERPRISE_ACR}\n"
        f"ACR_NAMESPACE=$(touch {bash_path(marker)})\n"
        "PUBLIC_BASE_URL=https://public.example.test\n"
        "COMPOSE_PROJECT_NAME=attacker-project\n",
        encoding="utf-8",
    )

    result = run_deploy(fixture, COMPOSE_PROJECT_NAME="attacker-project")

    assert result.returncode != 0
    assert "invalid deployment environment" in result.stderr
    assert not marker.exists()
    assert log_lines(fixture["docker_log"]) == []


def test_deploy_script_safely_preflights_production_login_configuration():
    content = read("scripts/deploy.sh")
    preflight = read("scripts/production-preflight.sh")

    assert 'source "$APP_ENV"' not in content
    assert 'done < "$app_env"' in preflight
    assert "SESSION_COOKIE_SECURE" in preflight
    assert "APP_ENCRYPTION_KEY" in preflight
    assert "GOOGLE_REDIRECT_URI" in preflight
    assert "SMTP_PASSWORD" in preflight
    assert "REPLACE_" in preflight


@pytest.mark.parametrize(
    ("production_env", "error_fragment"),
    [
        (valid_production_environment().replace("DEBUG=false", "DEBUG=true"), "DEBUG"),
        (
            valid_production_environment().replace(
                "SESSION_COOKIE_SECURE=true", "SESSION_COOKIE_SECURE=false"
            ),
            "SESSION_COOKIE_SECURE",
        ),
        (
            valid_production_environment().replace(
                "SESSION_COOKIE_SECURE=true", "SESSION_COOKIE_SECURE=0"
            ),
            "SESSION_COOKIE_SECURE",
        ),
        (
            valid_production_environment().replace(
                "SESSION_COOKIE_SECURE=true", "SESSION_COOKIE_SECURE=no"
            ),
            "SESSION_COOKIE_SECURE",
        ),
        (
            valid_production_environment().replace(
                "SESSION_COOKIE_SECURE=true", "SESSION_COOKIE_SECURE=off"
            ),
            "SESSION_COOKIE_SECURE",
        ),
        (
            valid_production_environment().replace(
                "SESSION_COOKIE_SECURE=true", "SESSION_COOKIE_SECURE="
            ),
            "SESSION_COOKIE_SECURE",
        ),
        (
            valid_production_environment().replace(
                "SESSION_COOKIE_SECURE=true", 'SESSION_COOKIE_SECURE="true"'
            ),
            "quoted",
        ),
        (
            valid_production_environment().replace(
                "SMTP_PASSWORD=password=$literal=with=equals",
                "SMTP_PASSWORD='password=$literal=with=equals'",
            ),
            "quoted",
        ),
        (
            valid_production_environment().replace(
                f"APP_ENCRYPTION_KEY={VALID_FERNET_KEY}",
                "APP_ENCRYPTION_KEY=                                            ",
            ),
            "Fernet",
        ),
        (
            valid_production_environment().replace(
                f"APP_ENCRYPTION_KEY={VALID_FERNET_KEY}",
                "APP_ENCRYPTION_KEY=REPLACE_WITH_KEY",
            ),
            "placeholder",
        ),
        (
            valid_production_environment().replace(
                "ADMIN_EMAILS=admin@zhiku-cloud.cn",
                "ADMIN_EMAILS=admin@example.com",
            ),
            "ADMIN_EMAILS",
        ),
        (
            valid_production_environment().replace(
                f"APP_ENCRYPTION_KEY={VALID_FERNET_KEY}",
                "APP_ENCRYPTION_KEY=short",
            ),
            "APP_ENCRYPTION_KEY",
        ),
        (
            "DEBUG=false\n"
            "SESSION_COOKIE_SECURE=true\n"
            "ADMIN_EMAILS=admin@zhiku-cloud.cn\n"
            f"APP_ENCRYPTION_KEY={VALID_FERNET_KEY}\n",
            "login method",
        ),
        (
            valid_production_environment().replace(
                "SMTP_PASSWORD=password=$literal=with=equals", "SMTP_PASSWORD="
            ),
            "SMTP",
        ),
        (
            valid_production_environment()
            + "GOOGLE_CLIENT_ID=client-id\n"
            + "GOOGLE_CLIENT_SECRET=\n"
            + "GOOGLE_REDIRECT_URI=https://zhiku-cloud.cn/system-auth/google/callback\n",
            "Google",
        ),
        (
            valid_production_environment()
            + "GOOGLE_CLIENT_ID=client-id\n"
            + "GOOGLE_CLIENT_SECRET=client-secret\n"
            + "GOOGLE_REDIRECT_URI=https://example.com/callback\n",
            "GOOGLE_REDIRECT_URI",
        ),
    ],
)
def test_deploy_script_rejects_unsafe_production_env_before_docker(
    tmp_path, production_env, error_fragment
):
    fixture = deployment_fixture(tmp_path)
    (Path(fixture["deploy_dir"]) / ".env.production").write_text(
        production_env, encoding="utf-8"
    )

    result = run_deploy(fixture)

    assert result.returncode != 0
    assert error_fragment in result.stderr
    assert log_lines(fixture["docker_log"]) == []


def test_deploy_script_accepts_complete_google_login_and_optional_equals(tmp_path):
    fixture = deployment_fixture(tmp_path)
    google_only = (
        "DEBUG=false\n"
        "SESSION_COOKIE_SECURE=true\n"
        "ADMIN_EMAILS=owner@zhiku-cloud.cn\n"
        f"APP_ENCRYPTION_KEY={VALID_FERNET_KEY}\n"
        "GOOGLE_CLIENT_ID=client-id.apps.googleusercontent.com\n"
        "GOOGLE_CLIENT_SECRET=secret=with=equals\n"
        "GOOGLE_REDIRECT_URI=https://zhiku-cloud.cn/system-auth/google/callback\n"
        "OPTIONAL_PROVIDER_VALUE=kept=with=equals\n"
    )
    (Path(fixture["deploy_dir"]) / ".env.production").write_text(
        google_only, encoding="utf-8"
    )

    result = run_deploy(fixture)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "registry",
    [
        "registry.cn-beijing.aliyuncs.com",
        "registry-vpc.cn-beijing.aliyuncs.com",
        "registry.cn-beijing.cr.aliyuncs.com",
        "test-instance-registry.cn-hangzhou.cr.aliyuncs.com",
        "your-instance-registry.cn-beijing.cr.aliyuncs.com",
    ],
)
def test_deploy_script_rejects_non_enterprise_or_placeholder_acr_before_docker(
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
    assert "Enterprise Edition" in result.stderr
    assert log_lines(fixture["docker_log"]) == []


def test_deploy_script_rejects_unknown_existing_frontend_before_mutation(tmp_path):
    fixture = deployment_fixture(tmp_path)

    result = run_deploy(fixture, FAKE_EXISTING_SERVICES="frontend")

    assert result.returncode != 0
    assert "valid current SHA" in result.stderr
    assert log_lines(fixture["tar_log"]) == []


def test_deploy_script_rejects_insufficient_backup_space_before_downtime(tmp_path):
    fixture = deployment_fixture(tmp_path)

    result = run_deploy(fixture, FAKE_AVAILABLE_KIB="1024")

    assert result.returncode != 0
    assert "insufficient free space" in result.stderr
    commands = log_lines(fixture["docker_log"])
    assert not any("stop backend" in command for command in commands)
    assert log_lines(fixture["tar_log"]) == []


def test_deploy_script_rechecks_space_after_image_pulls_before_downtime(tmp_path):
    fixture = deployment_fixture(tmp_path)

    result = run_deploy(
        fixture,
        FAKE_AVAILABLE_KIB="4194304",
        FAKE_AFTER_PULL_AVAILABLE_KIB="1024",
    )

    assert result.returncode != 0
    assert "insufficient free space" in result.stderr
    commands = log_lines(fixture["docker_log"])
    assert f"{TARGET_TAG}|pull backend frontend" in commands
    assert not any("stop backend" in command for command in commands)
    assert list((Path(fixture["root"]) / "backups").iterdir()) == []


def test_deploy_script_refuses_existing_transaction_before_runtime_mutation(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "transaction").write_text(
        "version=1\noperation=deploy\nphase=runtime\n", encoding="utf-8"
    )

    result = run_deploy(fixture)

    assert result.returncode != 0
    assert "recover-interrupted.sh" in result.stderr
    assert log_lines(fixture["docker_log"]) == []


@pytest.mark.parametrize(
    "public_url",
    [
        "http://public.example.test",
        "https://user:pass@public.example.test",
        "https://public.example.test/?query=1",
        "https://public.example.test/#fragment",
    ],
)
def test_deploy_script_rejects_unsafe_public_base_urls(tmp_path, public_url):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / ".env.deploy").write_text(
        f"ACR_REGISTRY={ENTERPRISE_ACR}\n"
        "ACR_NAMESPACE=zhiku\n"
        f"PUBLIC_BASE_URL={public_url}\n",
        encoding="utf-8",
    )

    result = run_deploy(fixture)

    assert result.returncode != 0
    assert "valid HTTPS URL" in result.stderr
    assert log_lines(fixture["docker_log"]) == []


def test_deploy_script_first_failure_stops_only_started_target_services(tmp_path):
    fixture = deployment_fixture(tmp_path)

    result = run_deploy(fixture, FAKE_CURL_FAIL_TAG=TARGET_TAG)

    assert result.returncode != 0
    commands = log_lines(fixture["docker_log"])
    assert commands.count(f"{TARGET_TAG}|stop backend") == 2
    assert f"{TARGET_TAG}|stop frontend" not in commands
    assert not any(command.startswith(f"{PREVIOUS_TAG}|") for command in commands)


@pytest.mark.parametrize(
    ("status", "body"),
    [("302", '{"status":"healthy"}'), ("200", '{"status":"degraded"}')],
)
def test_deploy_script_strict_public_health_triggers_rollback(tmp_path, status, body):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend",
        FAKE_POST_STOP_STATES="exited",
        FAKE_STRICT_TAG=TARGET_TAG,
        FAKE_PUBLIC_HEALTH_STATUS=status,
        FAKE_PUBLIC_HEALTH_BODY=body,
    )

    assert result.returncode != 0
    assert f"{PREVIOUS_TAG}|up -d --pull never backend" in log_lines(
        fixture["docker_log"]
    )


def test_deploy_script_sighup_during_backup_rolls_back_once(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend",
        FAKE_POST_STOP_STATES="exited",
        FAKE_TAR_SIGNAL="HUP",
    )

    assert result.returncode == 129
    commands = log_lines(fixture["docker_log"])
    assert commands.count(f"{PREVIOUS_TAG}|up -d --pull never backend") == 1
    assert (deploy_dir / "current-version").read_text().strip() == PREVIOUS_TAG


def test_deploy_script_signal_after_version_commit_restores_prior_state(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    older_tag = "3" * 40
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")
    (deploy_dir / "previous-version").write_text(older_tag, encoding="utf-8")

    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend",
        FAKE_POST_STOP_STATES="exited",
        FAKE_SIGNAL_ON_CURRENT="TERM",
    )

    assert result.returncode == 143
    commands = log_lines(fixture["docker_log"])
    assert commands.count(f"{PREVIOUS_TAG}|up -d --pull never backend") == 1
    assert (deploy_dir / "current-version").read_text().strip() == PREVIOUS_TAG
    assert (deploy_dir / "previous-version").read_text().strip() == older_tag


def test_deploy_script_backup_directory_failure_happens_before_runtime_mutation(
    tmp_path,
):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend",
        FAKE_POST_STOP_STATES="exited",
        FAKE_MKTEMP_DIR_EXIT="71",
    )

    assert result.returncode != 0
    commands = log_lines(fixture["docker_log"])
    assert f"{TARGET_TAG}|stop backend" not in commands
    assert not any("|up -d " in command for command in commands)


def test_deploy_script_failed_tar_removes_only_partial_backup(tmp_path):
    fixture = deployment_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / "current-version").write_text(PREVIOUS_TAG, encoding="utf-8")

    result = run_deploy(
        fixture,
        FAKE_EXISTING_SERVICES="backend",
        FAKE_POST_STOP_STATES="exited",
        FAKE_TAR_EXIT="75",
    )

    assert result.returncode != 0
    backups_dir = Path(fixture["root"]) / "backups"
    assert list(backups_dir.iterdir()) == []
    assert (Path(fixture["root"]) / "data" / "database.sqlite").is_file()


def test_deploy_script_rejects_old_compose_before_runtime_mutation(tmp_path):
    fixture = deployment_fixture(tmp_path)

    result = run_deploy(fixture, FAKE_COMPOSE_VERSION="2.29.9")

    assert result.returncode != 0
    assert "Docker Compose >= 2.30" in result.stderr
    assert log_lines(fixture["docker_log"]) == []


def create_application_sqlite(path: Path, marker: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE system_users (id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE knowledge_bases (id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE restore_marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO restore_marker (value) VALUES (?)", (marker,))
        connection.commit()
    finally:
        connection.close()


def create_chroma_sqlite(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE collections (id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO collections (id) VALUES ('collection-1')")
        connection.commit()
    finally:
        connection.close()


def sqlite_restore_marker(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute("SELECT value FROM restore_marker").fetchone()
    finally:
        connection.close()
    assert row is not None
    return str(row[0])


def make_restore_archive(
    path: Path, *, unsafe_symlink: bool = False, corrupt_database: str | None = None
) -> None:
    source = path.parent / "archive-source"
    chroma = source / "chroma_db"
    chroma.mkdir(parents=True, exist_ok=True)
    app_database = source / "bilibili_rag.db"
    chroma_database = chroma / "chroma.sqlite3"
    app_database.unlink(missing_ok=True)
    chroma_database.unlink(missing_ok=True)
    if corrupt_database == "app":
        app_database.write_bytes(b"not sqlite")
    else:
        create_application_sqlite(app_database, "new")
    if corrupt_database == "chroma":
        chroma_database.write_bytes(b"not sqlite")
    else:
        create_chroma_sqlite(chroma_database)

    with tarfile.open(path, "w:gz") as archive:
        archive.add(source / "bilibili_rag.db", arcname="./bilibili_rag.db")
        archive.add(chroma, arcname="./chroma_db")
        if unsafe_symlink:
            link = tarfile.TarInfo("./chroma_db/unsafe-link")
            link.type = tarfile.SYMTYPE
            link.linkname = "../../outside"
            archive.addfile(link)


def restore_fixture(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "restore-root"
    deploy_dir = root / "deploy"
    data_dir = root / "data"
    backups_dir = root / "backups"
    backup_dir = backups_dir / "20260719T000000Z-test"
    bin_dir = tmp_path / "restore-bin"
    for directory in [deploy_dir, data_dir / "chroma_db", backup_dir, bin_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    (root / "compose.production.yml").write_text("services: {}\n", encoding="utf-8")
    (deploy_dir / ".env.deploy").write_text(
        f"ACR_REGISTRY={ENTERPRISE_ACR}\n"
        "ACR_NAMESPACE=zhiku\n"
        "PUBLIC_BASE_URL=https://public.example.test\n",
        encoding="utf-8",
    )
    (deploy_dir / ".env.production").write_text(
        valid_production_environment(), encoding="utf-8"
    )
    (deploy_dir / "current-version").write_text(TARGET_TAG + "\n", encoding="utf-8")
    create_application_sqlite(data_dir / "bilibili_rag.db", "old")
    create_chroma_sqlite(data_dir / "chroma_db" / "chroma.sqlite3")
    archive = backup_dir / "data.tar.gz"
    make_restore_archive(archive)

    operation_log = tmp_path / "restore-operations.log"
    docker_counter = tmp_path / "restore-docker-counter"
    curl_counter = tmp_path / "restore-curl-counter"
    mv_counter = tmp_path / "restore-mv-counter"

    write_fake_tool(
        bin_dir,
        "docker",
        """#!/usr/bin/env bash
set -u
if [[ "$*" == "compose version --short" ]]; then
  printf '%s\n' "${FAKE_COMPOSE_VERSION:-2.30.0}"
  exit 0
fi
[[ "${1:-}" == compose ]] || exit 90
shift
project_name=""
while (( $# > 0 )); do
  case "$1" in
    --project-name) project_name="$2"; shift 2 ;;
    --project-directory|--env-file|-f) shift 2 ;;
    *) break ;;
  esac
done
[[ "$project_name" == zhiku-cloud ]] || exit 92
command_line="$*"
printf 'docker|%s|%s\n' "${IMAGE_TAG:-unset}" "$command_line" >> "$FAKE_OPERATION_LOG"
case "$command_line" in
  "stop backend"|"stop backend frontend") exit "${FAKE_STOP_EXIT:-0}" ;;
  "ps --all --format {{.State}} backend") printf '%s\n' "${FAKE_POST_STOP_STATES:-exited}" ;;
  "up -d --pull never backend"|"up -d --pull never frontend")
    count=0
    [[ -f "$FAKE_DOCKER_COUNTER" ]] && count="$(cat "$FAKE_DOCKER_COUNTER")"
    count=$((count + 1))
    printf '%s' "$count" > "$FAKE_DOCKER_COUNTER"
    if (( count <= ${FAKE_START_FAILURES:-0} )); then exit 71; fi
    ;;
  *) exit 93 ;;
esac
""",
    )
    write_fake_tool(
        bin_dir,
        "curl",
        """#!/usr/bin/env bash
set -u
url="${!#}"
count=0
[[ -f "$FAKE_CURL_COUNTER" ]] && count="$(cat "$FAKE_CURL_COUNTER")"
count=$((count + 1))
printf '%s' "$count" > "$FAKE_CURL_COUNTER"
printf 'curl|%s|%s\n' "${IMAGE_TAG:-unset}" "$url" >> "$FAKE_OPERATION_LOG"
if (( count <= ${FAKE_CURL_FAILURES:-0} )); then exit 22; fi
printf '{"status":"healthy"}\n200'
""",
    )
    write_fake_tool(
        bin_dir,
        "cp",
        """#!/usr/bin/env bash
printf 'cp|%s\n' "$*" >> "$FAKE_OPERATION_LOG"
[[ -z "${FAKE_CP_EXIT:-}" ]] || exit "$FAKE_CP_EXIT"
exec /usr/bin/cp "$@"
""",
    )
    write_fake_tool(
        bin_dir,
        "chown",
        """#!/usr/bin/env bash
printf 'chown|%s\n' "$*" >> "$FAKE_OPERATION_LOG"
[[ -z "${FAKE_CHOWN_EXIT:-}" ]] || exit "$FAKE_CHOWN_EXIT"
exit 0
""",
    )
    write_fake_tool(
        bin_dir,
        "mv",
        """#!/usr/bin/env bash
destination="${!#}"
if [[ "$destination" == */transaction ]]; then
  exec /usr/bin/mv "$@"
fi
count=0
[[ -f "$FAKE_MV_COUNTER" ]] && count="$(cat "$FAKE_MV_COUNTER")"
count=$((count + 1))
printf '%s' "$count" > "$FAKE_MV_COUNTER"
printf 'mv|%s\n' "$*" >> "$FAKE_OPERATION_LOG"
if [[ "$count" == "${FAKE_MV_FAIL_AT:-}" ]]; then exit 72; fi
/usr/bin/mv "$@" || exit $?
if [[ "$count" == "${FAKE_MV_SIGNAL_AT:-}" ]]; then
  kill -s "${FAKE_MV_SIGNAL:-HUP}" "$PPID"
  sleep 1
fi
""",
    )
    write_fake_tool(
        bin_dir,
        "flock",
        """#!/usr/bin/env bash
[[ "${FAKE_LOCK_HELD:-0}" == 1 ]] && exit 1
exit 0
""",
    )
    write_fake_tool(
        bin_dir,
        "df",
        """#!/usr/bin/env bash
printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n'
printf 'fake 8388608 0 %s 0%% /\n' "${FAKE_AVAILABLE_KIB:-4194304}"
""",
    )
    write_fake_tool(bin_dir, "sleep", "#!/usr/bin/env bash\nexit 0\n")

    env = os.environ.copy()
    env.update(
        {
            "ZHIKU_DEPLOY_ROOT": bash_path(root),
            "ZHIKU_RESTORE_PYTHON": bash_path(Path(sys.executable)),
            "ZHIKU_RESTORE_HTTP_ATTEMPTS": "2",
            "ZHIKU_RESTORE_HTTP_DELAY_SECONDS": "0",
            "FAKE_OPERATION_LOG": bash_path(operation_log),
            "FAKE_DOCKER_COUNTER": bash_path(docker_counter),
            "FAKE_CURL_COUNTER": bash_path(curl_counter),
            "FAKE_MV_COUNTER": bash_path(mv_counter),
        }
    )
    return {
        "root": root,
        "deploy_dir": deploy_dir,
        "data_dir": data_dir,
        "backups_dir": backups_dir,
        "archive": archive,
        "bin_dir": bin_dir,
        "operation_log": operation_log,
        "env": env,
    }


def run_restore(
    fixture: dict[str, object],
    archive: Path | None = None,
    *,
    include_argument: bool = True,
    **env_updates: str,
) -> subprocess.CompletedProcess:
    env = dict(fixture["env"])
    env.update(env_updates)
    command = [
        bash_executable(),
        "-c",
        'PATH="$1:$PATH"; export PATH; shift; exec bash "$@"',
        "restore-test",
        bash_path(Path(fixture["bin_dir"])),
        bash_path(RESTORE_SCRIPT),
    ]
    if include_argument:
        command.append(bash_path(archive or Path(fixture["archive"])))
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )


def run_recover(
    fixture: dict[str, object], **env_updates: str
) -> subprocess.CompletedProcess:
    env = dict(fixture["env"])
    env.update(env_updates)
    return subprocess.run(
        [
            bash_executable(),
            "-c",
            'PATH="$1:$PATH"; export PATH; exec bash "$2"',
            "recover-test",
            bash_path(Path(fixture["bin_dir"])),
            bash_path(RECOVER_SCRIPT),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )


def restore_operations(fixture: dict[str, object]) -> list[str]:
    return log_lines(fixture["operation_log"])


def assert_old_restore_data_is_active(fixture: dict[str, object]) -> None:
    data_dir = Path(fixture["data_dir"])
    assert sqlite_restore_marker(data_dir / "bilibili_rag.db") == "old"
    connection = sqlite3.connect(data_dir / "chroma_db" / "chroma.sqlite3")
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        connection.close()


def test_restore_script_rejects_missing_and_outside_backup_paths(tmp_path):
    fixture = restore_fixture(tmp_path)
    outside = tmp_path / "outside.tar.gz"
    shutil.copy2(fixture["archive"], outside)

    missing = run_restore(fixture, include_argument=False)
    outside_result = run_restore(fixture, outside)

    assert missing.returncode == 2
    assert outside_result.returncode != 0
    assert "must resolve inside" in outside_result.stderr
    assert restore_operations(fixture) == []


def test_restore_script_rejects_invalid_and_symlink_archives_before_downtime(tmp_path):
    fixture = restore_fixture(tmp_path)
    archive = Path(fixture["archive"])
    archive.write_bytes(b"not a tar archive")

    invalid = run_restore(fixture)
    make_restore_archive(archive, unsafe_symlink=True)
    unsafe = run_restore(fixture)

    assert invalid.returncode != 0
    assert unsafe.returncode != 0
    assert "unsafe archive" in unsafe.stderr
    assert list(Path(fixture["root"]).glob("data.restore.*")) == []
    assert not any("docker|" in line for line in restore_operations(fixture))


@pytest.mark.parametrize("database", ["app", "chroma"])
def test_restore_script_rejects_corrupt_sqlite_before_downtime(tmp_path, database):
    fixture = restore_fixture(tmp_path)
    make_restore_archive(Path(fixture["archive"]), corrupt_database=database)

    result = run_restore(fixture)

    assert result.returncode != 0
    assert "SQLite validation failed" in result.stderr
    assert not any("docker|" in line for line in restore_operations(fixture))


@pytest.mark.parametrize(
    "limit_env",
    [
        {"ZHIKU_RESTORE_MAX_MEMBERS": "1"},
        {"ZHIKU_RESTORE_MAX_BYTES": "1"},
    ],
)
def test_restore_script_rejects_archives_over_resource_limits_before_downtime(
    tmp_path, limit_env
):
    fixture = restore_fixture(tmp_path)

    result = run_restore(fixture, **limit_env)

    assert result.returncode != 0
    assert "archive resource limit exceeded" in result.stderr
    assert not any("docker|" in line for line in restore_operations(fixture))


def test_restore_script_rejects_insufficient_space_before_extraction_or_downtime(
    tmp_path,
):
    fixture = restore_fixture(tmp_path)

    result = run_restore(fixture, FAKE_AVAILABLE_KIB="1024")

    assert result.returncode != 0
    assert "insufficient free space" in result.stderr
    assert list(Path(fixture["root"]).glob("data.restore.*")) == []
    assert not any("docker|" in line for line in restore_operations(fixture))


def test_restore_script_refuses_existing_transaction_before_staging(tmp_path):
    fixture = restore_fixture(tmp_path)
    (Path(fixture["deploy_dir"]) / "transaction").write_text(
        "version=1\noperation=restore\nphase=prepared\n", encoding="utf-8"
    )

    result = run_restore(fixture)

    assert result.returncode != 0
    assert "recover-interrupted.sh" in result.stderr
    assert list(Path(fixture["root"]).glob("data.restore.*")) == []


def test_restore_script_rejects_invalid_current_sha_before_downtime(tmp_path):
    fixture = restore_fixture(tmp_path)
    (Path(fixture["deploy_dir"]) / "current-version").write_text(
        "latest\n", encoding="utf-8"
    )

    result = run_restore(fixture)

    assert result.returncode != 0
    assert "40-character SHA" in result.stderr
    assert restore_operations(fixture) == []


@pytest.mark.parametrize(
    ("file_name", "invalid_content", "error_fragment"),
    [
        (
            ".env.deploy",
            "ACR_REGISTRY=registry.cn-beijing.aliyuncs.com\n"
            "ACR_NAMESPACE=zhiku\n"
            "PUBLIC_BASE_URL=https://public.example.test\n",
            "Enterprise Edition",
        ),
        (
            ".env.production",
            valid_production_environment().replace(
                "SESSION_COOKIE_SECURE=true", 'SESSION_COOKIE_SECURE="true"'
            ),
            "quoted",
        ),
        (
            ".env.production",
            valid_production_environment().replace(
                "SMTP_PASSWORD=password=$literal=with=equals",
                "SMTP_PASSWORD='password=$literal=with=equals'",
            ),
            "quoted",
        ),
        (
            ".env.production",
            valid_production_environment().replace(
                f"APP_ENCRYPTION_KEY={VALID_FERNET_KEY}",
                "APP_ENCRYPTION_KEY=short",
            ),
            "Fernet",
        ),
        (
            ".env.production",
            valid_production_environment().replace(
                "ADMIN_EMAILS=admin@zhiku-cloud.cn",
                "ADMIN_EMAILS=admin@example.com",
            ),
            "ADMIN_EMAILS",
        ),
        (
            ".env.production",
            "DEBUG=false\n"
            "SESSION_COOKIE_SECURE=true\n"
            "ADMIN_EMAILS=admin@zhiku-cloud.cn\n"
            f"APP_ENCRYPTION_KEY={VALID_FERNET_KEY}\n",
            "login method",
        ),
    ],
)
def test_restore_script_reuses_production_preflight_before_staging_or_downtime(
    tmp_path, file_name, invalid_content, error_fragment
):
    fixture = restore_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    (deploy_dir / file_name).write_text(invalid_content, encoding="utf-8")

    result = run_restore(fixture)

    assert result.returncode != 0
    assert error_fragment in result.stderr
    assert list(Path(fixture["root"]).glob("data.restore.*")) == []
    assert list(Path(fixture["root"]).glob("data.safety.*")) == []
    assert not (deploy_dir / "transaction").exists()
    assert restore_operations(fixture) == []


@pytest.mark.parametrize(
    ("failure_env", "failure_value"),
    [("FAKE_CP_EXIT", "73"), ("FAKE_CHOWN_EXIT", "74")],
)
def test_restore_script_preparation_failures_do_not_stop_backend(
    tmp_path, failure_env, failure_value
):
    fixture = restore_fixture(tmp_path)

    result = run_restore(fixture, **{failure_env: failure_value})

    assert result.returncode != 0
    assert_old_restore_data_is_active(fixture)
    assert not any("docker|" in line for line in restore_operations(fixture))
    assert list(Path(fixture["root"]).glob("data.restore.*")) == []
    assert list(Path(fixture["root"]).glob("data.safety.*")) == []


@pytest.mark.parametrize(
    ("failure_env", "expected_start_count"),
    [
        ({"FAKE_MV_FAIL_AT": "2"}, 1),
        ({"FAKE_START_FAILURES": "1"}, 2),
        ({"FAKE_CURL_FAILURES": "2"}, 2),
    ],
)
def test_restore_script_mutation_failures_restore_old_data_and_backend(
    tmp_path, failure_env, expected_start_count
):
    fixture = restore_fixture(tmp_path)

    result = run_restore(fixture, **failure_env)

    assert result.returncode != 0
    assert_old_restore_data_is_active(fixture)
    operations = restore_operations(fixture)
    assert f"docker|{TARGET_TAG}|stop backend" in operations
    assert (
        operations.count(f"docker|{TARGET_TAG}|up -d --pull never backend")
        == expected_start_count
    )
    assert f"curl|{TARGET_TAG}|https://public.example.test/health" in operations


def test_restore_script_failed_safety_restore_leaves_backend_stopped(tmp_path):
    fixture = restore_fixture(tmp_path)

    result = run_restore(
        fixture,
        FAKE_CURL_FAILURES="2",
        FAKE_MV_FAIL_AT="4",
    )

    assert result.returncode != 0
    operations = restore_operations(fixture)
    assert operations.count(f"docker|{TARGET_TAG}|up -d --pull never backend") == 1
    assert operations.count(f"docker|{TARGET_TAG}|stop backend") == 2
    assert "backend left stopped" in result.stderr
    assert "old data:" in result.stderr
    safety_dirs = list(Path(fixture["root"]).glob("data.safety.*"))
    assert len(safety_dirs) == 1
    assert sqlite_restore_marker(safety_dirs[0] / "data" / "bilibili_rag.db") == ("old")


def test_restore_script_hup_after_swap_recovers_once(tmp_path):
    fixture = restore_fixture(tmp_path)

    result = run_restore(fixture, FAKE_MV_SIGNAL_AT="2", FAKE_MV_SIGNAL="HUP")

    assert result.returncode == 129
    assert_old_restore_data_is_active(fixture)
    operations = restore_operations(fixture)
    assert operations.count(f"docker|{TARGET_TAG}|up -d --pull never backend") == 1


def test_restore_script_hup_immediately_after_preserving_data_recovers(tmp_path):
    fixture = restore_fixture(tmp_path)

    result = run_restore(fixture, FAKE_MV_SIGNAL_AT="1", FAKE_MV_SIGNAL="HUP")

    assert result.returncode == 129
    assert_old_restore_data_is_active(fixture)
    operations = restore_operations(fixture)
    assert operations.count(f"docker|{TARGET_TAG}|up -d --pull never backend") == 1


def test_restore_script_success_swaps_data_and_keeps_unique_safety_copy(tmp_path):
    fixture = restore_fixture(tmp_path)

    result = run_restore(fixture)

    assert result.returncode == 0, result.stderr
    data_dir = Path(fixture["data_dir"])
    assert sqlite_restore_marker(data_dir / "bilibili_rag.db") == "new"
    safety_dirs = list(Path(fixture["root"]).glob("data.safety.*"))
    assert len(safety_dirs) == 1
    assert sqlite_restore_marker(safety_dirs[0] / "data" / "bilibili_rag.db") == ("old")
    operations = restore_operations(fixture)
    assert operations.count(f"docker|{TARGET_TAG}|up -d --pull never backend") == 1
    assert f"curl|{TARGET_TAG}|https://public.example.test/health" in operations


def test_restore_script_real_flock_blocks_concurrent_restore(tmp_path):
    has_flock = subprocess.run(
        [bash_executable(), "-lc", "command -v flock"],
        capture_output=True,
        check=False,
    )
    if has_flock.returncode != 0:
        pytest.skip("real flock is unavailable in this Git Bash environment")

    fixture = restore_fixture(tmp_path)
    (Path(fixture["bin_dir"]) / "flock").unlink()
    lock_path = Path(fixture["deploy_dir"]) / "deploy.lock"
    marker = tmp_path / "real-flock-held"
    holder = subprocess.Popen(
        [
            bash_executable(),
            "-c",
            'exec 9>"$1"; flock 9; printf locked > "$2"; sleep 4',
            "flock-holder",
            bash_path(lock_path),
            bash_path(marker),
        ],
        cwd=PROJECT_ROOT,
    )
    try:
        deadline = time.monotonic() + 2
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.exists(), "real flock holder did not acquire the lock"

        result = run_restore(fixture)

        assert result.returncode != 0
        assert "already in progress" in result.stderr
        assert restore_operations(fixture) == []
    finally:
        holder.terminate()
        holder.wait(timeout=3)


def create_restore_data_tree(path: Path, marker: str) -> None:
    (path / "chroma_db").mkdir(parents=True)
    create_application_sqlite(path / "bilibili_rag.db", marker)
    create_chroma_sqlite(path / "chroma_db" / "chroma.sqlite3")


def write_restore_transaction(
    fixture: dict[str, object], staged_data: Path, safety_parent: Path, phase: str
) -> None:
    (Path(fixture["deploy_dir"]) / "transaction").write_text(
        "version=1\n"
        "operation=restore\n"
        f"phase={phase}\n"
        f"current_tag={TARGET_TAG}\n"
        f"staged_data={bash_path(staged_data)}\n"
        f"safety_parent={bash_path(safety_parent)}\n",
        encoding="utf-8",
    )


def test_recovery_reconciles_restore_before_data_swap(tmp_path):
    fixture = restore_fixture(tmp_path)
    root = Path(fixture["root"])
    staged = root / "data.restore.test"
    safety = root / "data.safety.test"
    create_restore_data_tree(staged, "new")
    safety.mkdir()
    write_restore_transaction(fixture, staged, safety, "prepared")

    result = run_recover(fixture)

    assert result.returncode == 0, result.stderr
    assert_old_restore_data_is_active(fixture)
    assert not staged.exists()
    assert not safety.exists()
    assert not (Path(fixture["deploy_dir"]) / "transaction").exists()


def test_recovery_reconciles_restore_between_data_renames(tmp_path):
    fixture = restore_fixture(tmp_path)
    root = Path(fixture["root"])
    staged = root / "data.restore.test"
    safety = root / "data.safety.test"
    create_restore_data_tree(staged, "new")
    safety.mkdir()
    Path(fixture["data_dir"]).rename(safety / "data")
    write_restore_transaction(fixture, staged, safety, "prepared")

    result = run_recover(fixture)

    assert result.returncode == 0, result.stderr
    assert_old_restore_data_is_active(fixture)
    assert not staged.exists()
    assert not safety.exists()
    assert not (Path(fixture["deploy_dir"]) / "transaction").exists()


def test_recovery_reconciles_restore_after_new_data_is_active(tmp_path):
    fixture = restore_fixture(tmp_path)
    root = Path(fixture["root"])
    staged = root / "data.restore.test"
    safety = root / "data.safety.test"
    create_restore_data_tree(staged, "new")
    safety.mkdir()
    Path(fixture["data_dir"]).rename(safety / "data")
    staged.rename(Path(fixture["data_dir"]))
    write_restore_transaction(fixture, staged, safety, "new_active")

    result = run_recover(fixture)

    assert result.returncode == 0, result.stderr
    assert_old_restore_data_is_active(fixture)
    assert (
        sqlite_restore_marker(safety / "failed-restored-data" / "bilibili_rag.db")
        == "new"
    )
    assert not (Path(fixture["deploy_dir"]) / "transaction").exists()


def test_recovery_restore_is_idempotent_after_rollback_then_restart_failure(tmp_path):
    fixture = restore_fixture(tmp_path)
    root = Path(fixture["root"])
    staged = root / "data.restore.test"
    safety = root / "data.safety.test"
    create_restore_data_tree(staged, "new")
    safety.mkdir()
    Path(fixture["data_dir"]).rename(safety / "data")
    staged.rename(Path(fixture["data_dir"]))
    (safety / "current-version").write_text(TARGET_TAG + "\n", encoding="utf-8")
    write_restore_transaction(fixture, staged, safety, "new_active")

    first = run_recover(fixture, FAKE_START_FAILURES="1")

    assert first.returncode != 0
    assert_old_restore_data_is_active(fixture)
    assert (safety / "failed-restored-data").is_dir()
    transaction = Path(fixture["deploy_dir"]) / "transaction"
    assert "phase=rollback_ready\n" in transaction.read_text(encoding="utf-8")
    assert (safety / "current-version").exists()

    second = run_recover(fixture)

    assert second.returncode == 0, second.stderr
    assert_old_restore_data_is_active(fixture)
    assert not transaction.exists()
    assert not (safety / "current-version").exists()


def test_recovery_restore_remains_reentrant_after_repeated_backend_start_failure(
    tmp_path,
):
    fixture = restore_fixture(tmp_path)
    root = Path(fixture["root"])
    staged = root / "data.restore.test"
    safety = root / "data.safety.test"
    create_restore_data_tree(staged, "new")
    safety.mkdir()
    Path(fixture["data_dir"]).rename(safety / "data")
    staged.rename(Path(fixture["data_dir"]))
    (safety / "current-version").write_text(TARGET_TAG + "\n", encoding="utf-8")
    write_restore_transaction(fixture, staged, safety, "new_active")
    transaction = Path(fixture["deploy_dir"]) / "transaction"

    first = run_recover(fixture, FAKE_START_FAILURES="2")
    second = run_recover(fixture, FAKE_START_FAILURES="2")

    assert first.returncode != 0
    assert second.returncode != 0
    assert_old_restore_data_is_active(fixture)
    assert "phase=rollback_ready\n" in transaction.read_text(encoding="utf-8")
    assert (safety / "current-version").exists()

    third = run_recover(fixture)

    assert third.returncode == 0, third.stderr
    assert_old_restore_data_is_active(fixture)
    assert not transaction.exists()
    assert not (safety / "current-version").exists()


def test_recovery_resumes_phase_confirmed_active_only_rollback_after_start_failure(
    tmp_path,
):
    fixture = restore_fixture(tmp_path)
    root = Path(fixture["root"])
    staged = root / "data.restore.test"
    safety = root / "data.safety.test"
    write_restore_transaction(fixture, staged, safety, "rollback_ready")
    transaction = Path(fixture["deploy_dir"]) / "transaction"

    first = run_recover(fixture, FAKE_START_FAILURES="1")

    assert first.returncode != 0
    assert_old_restore_data_is_active(fixture)
    assert "phase=rollback_ready\n" in transaction.read_text(encoding="utf-8")
    assert not staged.exists()
    assert not safety.exists()

    second = run_recover(fixture)

    assert second.returncode == 0, second.stderr
    assert_old_restore_data_is_active(fixture)
    assert not transaction.exists()


def test_recovery_rejects_active_only_restore_state_without_rollback_phase(tmp_path):
    fixture = restore_fixture(tmp_path)
    root = Path(fixture["root"])
    staged = root / "data.restore.test"
    safety = root / "data.safety.test"
    write_restore_transaction(fixture, staged, safety, "new_active")

    result = run_recover(fixture)

    assert result.returncode != 0
    assert "backend left stopped" in result.stderr
    assert_old_restore_data_is_active(fixture)
    assert (Path(fixture["deploy_dir"]) / "transaction").exists()
    assert not any(
        "up -d --pull never backend" in line for line in restore_operations(fixture)
    )


def test_recovery_restores_previous_images_and_version_after_interrupted_deploy(
    tmp_path,
):
    fixture = restore_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    older_tag = "3" * 40
    (deploy_dir / "current-version").write_text(TARGET_TAG + "\n", encoding="utf-8")
    (deploy_dir / "previous-version").write_text(PREVIOUS_TAG + "\n", encoding="utf-8")
    backup_dir = Path(fixture["backups_dir"]) / f"20260719T010203Z-{TARGET_TAG}.test"
    backup_dir.mkdir()
    (deploy_dir / "transaction").write_text(
        "version=1\n"
        "operation=deploy\n"
        "phase=runtime\n"
        f"target_tag={TARGET_TAG}\n"
        f"previous_tag={PREVIOUS_TAG}\n"
        f"original_previous_tag={older_tag}\n"
        f"backup_dir={bash_path(backup_dir)}\n",
        encoding="utf-8",
    )

    result = run_recover(fixture)

    assert result.returncode == 0, result.stderr
    operations = restore_operations(fixture)
    assert f"docker|{PREVIOUS_TAG}|up -d --pull never backend" in operations
    assert f"docker|{PREVIOUS_TAG}|up -d --pull never frontend" in operations
    assert (deploy_dir / "current-version").read_text().strip() == PREVIOUS_TAG
    assert (deploy_dir / "previous-version").read_text().strip() == older_tag
    assert not backup_dir.exists()
    assert not (deploy_dir / "transaction").exists()


def test_recovery_deploy_cleans_only_known_partial_backup_after_hard_interrupt(
    tmp_path,
):
    fixture = restore_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    backup_dir = Path(fixture["backups_dir"]) / f"20260719T010203Z-{TARGET_TAG}.deadbe"
    backup_dir.mkdir()
    (backup_dir / "data.tar.gz.partial").write_text("partial", encoding="utf-8")
    (deploy_dir / "transaction").write_text(
        "version=1\n"
        "operation=deploy\n"
        "phase=runtime\n"
        f"target_tag={TARGET_TAG}\n"
        f"previous_tag={PREVIOUS_TAG}\n"
        "original_previous_tag=none\n"
        f"backup_dir={bash_path(backup_dir)}\n",
        encoding="utf-8",
    )

    result = run_recover(fixture)

    assert result.returncode == 0, result.stderr
    assert not backup_dir.exists()
    assert (Path(fixture["backups_dir"]) / "20260719T000000Z-test").is_dir()
    assert not (deploy_dir / "transaction").exists()


def test_recovery_deploy_retains_completed_backup(tmp_path):
    fixture = restore_fixture(tmp_path)
    deploy_dir = Path(fixture["deploy_dir"])
    backup_dir = (
        Path(fixture["backups_dir"]) / f"20260719T010203Z-{TARGET_TAG}.complete"
    )
    backup_dir.mkdir()
    (backup_dir / "data.tar.gz").write_text("complete", encoding="utf-8")
    (backup_dir / "previous-image-tag").write_text(PREVIOUS_TAG, encoding="utf-8")
    (deploy_dir / "transaction").write_text(
        "version=1\n"
        "operation=deploy\n"
        "phase=runtime\n"
        f"target_tag={TARGET_TAG}\n"
        f"previous_tag={PREVIOUS_TAG}\n"
        "original_previous_tag=none\n"
        f"backup_dir={bash_path(backup_dir)}\n",
        encoding="utf-8",
    )

    result = run_recover(fixture)

    assert result.returncode == 0, result.stderr
    assert (backup_dir / "data.tar.gz").is_file()
    assert (backup_dir / "previous-image-tag").is_file()
    assert not (deploy_dir / "transaction").exists()


def test_recovery_rejects_traversal_marker_without_deleting_active_data(tmp_path):
    fixture = restore_fixture(tmp_path)
    root = Path(fixture["root"])
    (root / "data.restore.attacker").mkdir()
    safety = root / "data.safety.test"
    safety.mkdir()
    traversal = f"{bash_path(root)}/data.restore.attacker/../data"
    (Path(fixture["deploy_dir"]) / "transaction").write_text(
        "version=1\n"
        "operation=restore\n"
        "phase=prepared\n"
        f"current_tag={TARGET_TAG}\n"
        f"staged_data={traversal}\n"
        f"safety_parent={bash_path(safety)}\n",
        encoding="utf-8",
    )

    result = run_recover(fixture)

    assert result.returncode != 0
    assert_old_restore_data_is_active(fixture)
    assert (Path(fixture["deploy_dir"]) / "transaction").exists()
    assert restore_operations(fixture) == []


def test_nginx_example_routes_tls_traffic_to_loopback_services():
    content = read("deploy/nginx/zhiku-cloud.conf.example")

    assert "limit_req_zone" in content
    assert "http {}" in content
    assert "listen 80;" in content
    assert content.count("server_name zhiku-cloud.cn www.zhiku-cloud.cn;") == 1
    assert content.count("server_name zhiku-cloud.cn;") == 1
    assert content.count("server_name www.zhiku-cloud.cn;") == 1
    assert "return 301 https://zhiku-cloud.cn$request_uri;" in content
    assert content.count("listen 443 ssl") == 2
    assert "ssl_certificate" in content
    assert "ssl_certificate_key" in content
    assert "certificate must cover both" in content
    assert "proxy_pass http://127.0.0.1:8000;" in content
    assert "proxy_pass http://127.0.0.1:3000;" in content
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" not in content
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in content


def test_nginx_example_limits_send_code_and_covers_every_backend_prefix():
    content = read("deploy/nginx/zhiku-cloud.conf.example")
    send_code_block = content.split("location = /system-auth/send-code {", maxsplit=1)[
        1
    ].split("}", maxsplit=1)[0]
    backend_locations = "\n".join(
        line.strip()
        for line in content.splitlines()
        if line.strip().startswith(("location = /", "location ~ ^/"))
    )

    assert "limit_req_zone $binary_remote_addr zone=send_code_per_ip" in content
    assert "limit_req zone=send_code_per_ip" in send_code_block
    assert "limit_req_status 429;" in send_code_block
    assert "proxy_pass http://127.0.0.1:8000;" in send_code_block
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in send_code_block

    for prefix in [
        "health",
        "docs",
        "redoc",
        "openapi.json",
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
        nginx_pattern = prefix.replace(".", r"\.")
        assert nginx_pattern in backend_locations


def test_nginx_example_scopes_upload_and_streaming_settings():
    content = read("deploy/nginx/zhiku-cloud.conf.example")
    upload_block = content.split("location ~ ^/imports/local-video/?$ {", maxsplit=1)[
        1
    ].split("}", maxsplit=1)[0]
    chat_block = content.split("location ~ ^/chat(?:/|$) {", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]
    ordinary_api_block = content.split("location ~ ^/(?:", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]

    assert "client_max_body_size 10m;" in content
    assert "client_max_body_size 1g;" in upload_block
    assert "proxy_request_buffering off;" in upload_block
    assert "proxy_read_timeout 900s;" in upload_block
    assert "proxy_buffering off;" in chat_block
    assert "proxy_buffering off;" not in ordinary_api_block
    assert "client_max_body_size 1g;" not in ordinary_api_block


def test_nginx_example_prioritizes_knowledge_base_streaming_route():
    content = read("deploy/nginx/zhiku-cloud.conf.example")
    stream_header = "location ~ ^/knowledge-bases/[0-9]+/chat/stream(?:/|$) {"
    generic_header = "location ~ ^/(?:health|docs|redoc|openapi\\.json"
    stream_block = content.split(stream_header, maxsplit=1)[1].split("}", maxsplit=1)[0]

    assert content.index(stream_header) < content.index(generic_header)
    assert "proxy_pass http://127.0.0.1:8000;" in stream_block
    assert "proxy_buffering off;" in stream_block
    assert "proxy_read_timeout 300s;" in stream_block


def test_production_environment_example_has_safe_minimum_login_configuration():
    content = read("deploy/.env.production.example")

    for expected in [
        "DEBUG=false",
        "SESSION_COOKIE_SECURE=true",
        "DATABASE_URL=sqlite+aiosqlite:///./data/bilibili_rag.db",
        "CHROMA_PERSIST_DIRECTORY=./data/chroma_db",
        "ADMIN_EMAILS=REPLACE_WITH_ADMIN_EMAIL",
        "APP_ENCRYPTION_KEY=REPLACE_WITH_GENERATED_FERNET_KEY",
        "SMTP_HOST=REPLACE_WITH_SMTP_HOST",
        "SMTP_PORT=587",
        "SMTP_USER=REPLACE_WITH_SMTP_USER",
        "SMTP_PASSWORD=REPLACE_WITH_SMTP_PASSWORD",
        "SMTP_FROM=REPLACE_WITH_SMTP_FROM",
        "SMTP_USE_TLS=true",
        "GOOGLE_CLIENT_ID=REPLACE_WITH_GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET=REPLACE_WITH_GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI=https://zhiku-cloud.cn/system-auth/google/callback",
    ]:
        assert expected in content

    assert "base64.urlsafe_b64encode(secrets.token_bytes(32))" in content
    assert "root .env.example" in content
    assert "REAL_SECRET" not in content


def test_restore_script_has_strict_safe_contract_and_linux_mode():
    content = read("scripts/restore-data.sh")

    assert "set -Eeuo pipefail" in content
    assert "umask 077" in content
    assert "(( $# != 1 ))" in content
    assert 'DEPLOY_ROOT="${ZHIKU_DEPLOY_ROOT:-/opt/zhiku-cloud}"' in content
    assert "^[0-9a-f]{40}$" in content
    assert "deploy.lock" in content
    assert "--project-name zhiku-cloud" in content
    assert "--pull never backend" in content
    assert "trap 'on_signal 129' HUP" in content
    assert "trap 'on_signal 130' INT" in content
    assert "trap 'on_signal 143' TERM" in content
    assert "compose down" not in content
    assert "down -v" not in content
    assert 'rm -rf -- "$path"' in content
    assert '"$DEPLOY_ROOT"/data.restore.*)' in content
    assert 'rm -rf -- "$DEPLOY_ROOT"' not in content
    assert 'rm -rf -- "$DATA_DIR"' not in content
    assert "\r\n" not in content
    assert "ZHIKU_RESTORE_MAX_MEMBERS" in content
    assert "ZHIKU_RESTORE_MAX_BYTES" in content
    assert "PRAGMA integrity_check" in content
    assert "system_users" in content
    assert "knowledge_bases" in content
    assert "chroma.sqlite3" in content
    lock_index = content.index("flock -n 9")
    assert lock_index < content.index("CURRENT_TAG=")
    preflight_index = content.index('production_preflight "$DEPLOY_ENV" "$APP_ENV"')
    staging_index = content.index('mktemp -d "$DEPLOY_ROOT/data.restore.')
    marker_index = content.index("write_restore_marker prepared")
    stop_index = content.index("compose stop backend", marker_index)
    assert preflight_index < staging_index < marker_index < stop_index
    index_entry = subprocess.run(
        ["git", "ls-files", "--stage", "scripts/restore-data.sh"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert index_entry.startswith("100755 ")


def test_container_production_runbook_documents_safe_exact_sha_operations():
    content = read("docs/deployment/container-production.md")

    for required in [
        "北京",
        "ACR_REGISTRY",
        "ACR_USERNAME",
        "ACR_PASSWORD",
        "ACR_NAMESPACE",
        "分支保护",
        "CI",
        "Publish Images",
        "/opt/zhiku-cloud",
        ".env.production",
        "chmod 600",
        "docker login",
        "40 位",
        "previous-version",
        "data.tar.gz",
        "/video-notes",
        "latest",
        "不具备原子性",
        "不自动 SSH",
        "拉取专用",
        "FORWARDED_ALLOW_IPS=*",
        "仅绑定 `127.0.0.1:8000`",
        "API 文档",
        "scripts/restore-data.sh",
        "deploy/.env.production.example",
        "0700",
        "Docker Compose 网络",
        "生产预检",
        "至少一种登录方式",
    ]:
        assert required in content

    for command_fragment in [
        "scripts/deploy.sh",
        "docker compose",
        "nginx -t",
        "systemctl reload nginx",
        "127.0.0.1:8000",
        "127.0.0.1:3000",
    ]:
        assert command_fragment in content

    assert "镜像回滚不会恢复数据" in content
    assert "./scripts/restore-data.sh" in content
    assert "安全副本" in content
    assert "tar -xzf" not in content
    assert "mv /opt/zhiku-cloud/data" not in content
    assert "down -v" not in content


def test_container_runbook_requires_immutable_acr_and_operational_disk_safety():
    content = read("docs/deployment/container-production.md")

    assert (
        "https://help.aliyun.com/zh/acr/user-guide/turn-on-immutable-image-version"
        in content
    )
    assert "zhiku-backend" in content and "zhiku-frontend" in content
    assert "不可变" in content
    assert "重新运行" in content and "不会覆盖" in content
    assert "Docker Compose 2.30" in content
    assert "最新 10" in content
    assert "异机" in content
    assert "df -h" in content
    assert "recover-interrupted.sh" in content
    assert "transaction" in content
    assert "down -v" not in content


def test_container_runbook_requires_beijing_acr_enterprise_edition():
    content = read("docs/deployment/container-production.md")

    assert "ACR 企业版" in content
    assert "华北 2（北京）" in content
    assert "your-instance-registry.cn-beijing.cr.aliyuncs.com" in content
    assert "个人版" in content
    assert "不支持生产" in content
    assert "无 SLA" in content
    assert (
        "https://help.aliyun.com/zh/acr/product-overview/differences-between-personal-edition-instances-and-enterprise-edition-instances"
        in content
    )


def test_readme_links_the_production_runbook_next_to_docker_section():
    content = read("README.md")
    docker_index = content.index("**Docker Compose**")
    runbook_link = "[容器化生产部署手册](docs/deployment/container-production.md)"
    link_index = content.index(runbook_link)

    assert docker_index < link_index < content.index("---", docker_index)
