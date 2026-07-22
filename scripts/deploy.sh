#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

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

readonly DEPLOY_ROOT="${ZHIKU_DEPLOY_ROOT:-/opt/zhiku-cloud}"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly PRODUCTION_PREFLIGHT="$SCRIPT_DIR/production-preflight.sh"
readonly COMPOSE_FILE="$DEPLOY_ROOT/compose.production.yml"
readonly DEPLOY_DIR="$DEPLOY_ROOT/deploy"
readonly DEPLOY_ENV="$DEPLOY_DIR/.env.deploy"
readonly APP_ENV="$DEPLOY_DIR/.env.production"
readonly DATA_DIR="$DEPLOY_ROOT/data"
readonly LOG_DIR="$DEPLOY_ROOT/logs"
readonly BACKUPS_DIR="$DEPLOY_ROOT/backups"
readonly CURRENT_FILE="$DEPLOY_DIR/current-version"
readonly PREVIOUS_FILE="$DEPLOY_DIR/previous-version"
readonly TRANSACTION_FILE="$DEPLOY_DIR/transaction"
readonly HTTP_ATTEMPTS="${ZHIKU_DEPLOY_HTTP_ATTEMPTS:-30}"
readonly HTTP_DELAY_SECONDS="${ZHIKU_DEPLOY_HTTP_DELAY_SECONDS:-2}"
readonly DISK_RESERVE_BYTES="${ZHIKU_DEPLOY_DISK_RESERVE_BYTES:-2147483648}"

if [[ ! "$HTTP_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] ||
  [[ ! "$HTTP_DELAY_SECONDS" =~ ^[0-9]+$ ]] ||
  [[ ! "$DISK_RESERVE_BYTES" =~ ^[0-9]+$ ]]; then
  echo "invalid deployment health retry configuration" >&2
  exit 2
fi

for command_name in docker curl tar flock mktemp du df awk python3; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "missing required command: $command_name" >&2
    exit 3
  }
done

for required_file in "$PRODUCTION_PREFLIGHT" "$COMPOSE_FILE" "$DEPLOY_ENV" "$APP_ENV"; do
  [[ -f "$required_file" ]] || {
    echo "missing required deployment file: $required_file" >&2
    exit 4
  }
done

# shellcheck source=production-preflight.sh
source "$PRODUCTION_PREFLIGHT"
production_preflight "$DEPLOY_ENV" "$APP_ENV"
readonly ACR_REGISTRY ACR_NAMESPACE PUBLIC_BASE_URL

INITIAL_CURRENT_TAG=""
if [[ -f "$CURRENT_FILE" ]]; then
  INITIAL_CURRENT_TAG="$(tr -d '[:space:]' < "$CURRENT_FILE")"
fi
if [[ "$INITIAL_CURRENT_TAG" =~ ^[0-9a-f]{40}$ ]]; then
  readonly INITIAL_HAS_CURRENT_TAG=true
else
  INITIAL_CURRENT_TAG=""
  readonly INITIAL_HAS_CURRENT_TAG=false
fi
readonly INITIAL_CURRENT_TAG

if [[ -e "$TRANSACTION_FILE" ]]; then
  echo "an interrupted transaction exists; run $DEPLOY_ROOT/scripts/recover-interrupted.sh" >&2
  exit 5
fi

if [[ "$INITIAL_HAS_CURRENT_TAG" == true && "$TARGET_TAG" == "$INITIAL_CURRENT_TAG" && "$ALLOW_REDEPLOY" == false ]]; then
  echo "target SHA is already current; use --allow-redeploy only for an intentional redeploy" >&2
  exit 2
fi

mkdir -p "$DEPLOY_DIR" "$DATA_DIR" "$LOG_DIR" "$BACKUPS_DIR"
exec 9>"$DEPLOY_DIR/deploy.lock"
if ! flock -n 9; then
  echo "another deployment is already in progress" >&2
  exit 5
fi
if [[ -e "$TRANSACTION_FILE" ]]; then
  echo "an interrupted transaction exists; run $DEPLOY_ROOT/scripts/recover-interrupted.sh" >&2
  exit 5
fi

ORIGINAL_CURRENT_EXISTS=false
ORIGINAL_CURRENT_CONTENT=""
if [[ -f "$CURRENT_FILE" ]]; then
  ORIGINAL_CURRENT_EXISTS=true
  ORIGINAL_CURRENT_CONTENT="$(cat "$CURRENT_FILE")"
fi
readonly ORIGINAL_CURRENT_EXISTS ORIGINAL_CURRENT_CONTENT

PREVIOUS_TAG="$(printf '%s' "$ORIGINAL_CURRENT_CONTENT" | tr -d '[:space:]')"
if [[ "$PREVIOUS_TAG" =~ ^[0-9a-f]{40}$ ]]; then
  HAS_PREVIOUS=true
else
  PREVIOUS_TAG=""
  HAS_PREVIOUS=false
fi

if [[ "$HAS_PREVIOUS" == true && "$TARGET_TAG" == "$PREVIOUS_TAG" && "$ALLOW_REDEPLOY" == false ]]; then
  echo "target SHA is already current; use --allow-redeploy only for an intentional redeploy" >&2
  exit 2
fi
readonly PREVIOUS_TAG HAS_PREVIOUS

if ! COMPOSE_VERSION="$(docker compose version --short 2>/dev/null)"; then
  echo "Docker Compose >= 2.30 is required" >&2
  exit 3
fi
COMPOSE_VERSION="${COMPOSE_VERSION#v}"
IFS=. read -r COMPOSE_MAJOR COMPOSE_MINOR _ <<<"$COMPOSE_VERSION"
if [[ ! "$COMPOSE_MAJOR" =~ ^[0-9]+$ || ! "$COMPOSE_MINOR" =~ ^[0-9]+$ ]] ||
  (( COMPOSE_MAJOR < 2 || (COMPOSE_MAJOR == 2 && COMPOSE_MINOR < 30) )); then
  echo "Docker Compose >= 2.30 is required; found $COMPOSE_VERSION" >&2
  exit 3
fi
readonly COMPOSE_VERSION

compose() {
  docker compose \
    --project-name zhiku-cloud \
    --project-directory "$DEPLOY_ROOT" \
    --env-file "$DEPLOY_ENV" \
    -f "$COMPOSE_FILE" \
    "$@"
}

wait_http() {
  local url="$1"
  local attempts="${2:-$HTTP_ATTEMPTS}"
  local delay_seconds="${3:-$HTTP_DELAY_SECONDS}"
  local expected_body="${4:-}"
  local attempt response status body compact_body
  local -a curl_options=(
    --fail
    --silent
    --show-error
    --max-time 5
    --write-out $'\n%{http_code}'
  )

  if [[ "$url" == https://* ]]; then
    curl_options+=(--proto '=https' --max-redirs 0)
  fi

  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if response="$(curl "${curl_options[@]}" "$url")"; then
      status="${response##*$'\n'}"
      body="${response%$'\n'*}"
      if [[ "$status" == 200 ]]; then
        if [[ -z "$expected_body" ]]; then
          return 0
        fi
        compact_body="$(printf '%s' "$body" | tr -d '[:space:]')"
        if [[ "$compact_body" == "$expected_body" ]]; then
          return 0
        fi
      fi
    fi
    if (( attempt < attempts )); then
      sleep "$delay_seconds"
    fi
  done

  echo "health check failed: $url" >&2
  return 1
}

wait_version_json() {
  local url="$1"
  local expected_sha="$2"
  local require_healthy="${3:-false}"
  local attempts="${4:-$HTTP_ATTEMPTS}"
  local delay_seconds="${5:-$HTTP_DELAY_SECONDS}"
  local attempt response status body
  local -a curl_options=(
    --fail
    --silent
    --show-error
    --max-time 5
    --write-out $'\n%{http_code}'
  )

  if [[ "$url" == https://* ]]; then
    curl_options+=(--proto '=https' --max-redirs 0)
  fi

  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if response="$(curl "${curl_options[@]}" "$url")"; then
      status="${response##*$'\n'}"
      body="${response%$'\n'*}"
      if [[ "$status" == 200 ]] &&
        printf '%s' "$body" | python3 -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, UnicodeDecodeError):
    raise SystemExit(1)
if not isinstance(payload, dict) or payload.get("version") != sys.argv[1]:
    raise SystemExit(1)
if sys.argv[2] == "true" and payload.get("status") != "healthy":
    raise SystemExit(1)
' "$expected_sha" "$require_healthy" 2>/dev/null; then
        return 0
      fi
    fi
    if (( attempt < attempts )); then
      sleep "$delay_seconds"
    fi
  done

  echo "version check failed: $url (expected SHA $expected_sha)" >&2
  return 1
}

verify_service_image() {
  local service="$1"
  local expected_sha="$2"
  local expected_image actual_image

  expected_image="${ACR_REGISTRY}/${ACR_NAMESPACE}/zhiku-${service}:${expected_sha}"
  actual_image="$(compose ps --format '{{.Image}}' "$service")" || actual_image=""
  if [[ "$actual_image" != "$expected_image" ]]; then
    echo "$service image mismatch: expected $expected_image, got ${actual_image:-<empty>}" >&2
    return 1
  fi
}

verify_runtime_version() {
  local expected_sha="$1"

  # Prove the immutable image identities first, then local responses, then the
  # public reverse-proxy responses so no version state is committed on drift.
  verify_service_image backend "$expected_sha" || return 1
  verify_service_image frontend "$expected_sha" || return 1
  wait_version_json "http://127.0.0.1:8000/health" "$expected_sha" true || return 1
  wait_version_json "http://127.0.0.1:3000/version.json" "$expected_sha" || return 1
  wait_version_json "${PUBLIC_BASE_URL%/}/health" "$expected_sha" true || return 1
  wait_version_json "${PUBLIC_BASE_URL%/}/version.json" "$expected_sha"
}

atomic_write() {
  local value="$1"
  local destination="$2"
  local temporary

  temporary="$(mktemp "${destination}.tmp.XXXXXX")" || return 1
  if ! printf '%s\n' "$value" > "$temporary"; then
    rm -f "$temporary"
    return 1
  fi
  if ! mv -- "$temporary" "$destination"; then
    rm -f "$temporary"
    return 1
  fi
}

ORIGINAL_PREVIOUS_EXISTS=false
ORIGINAL_PREVIOUS_CONTENT=""
if [[ -f "$PREVIOUS_FILE" ]]; then
  ORIGINAL_PREVIOUS_EXISTS=true
  ORIGINAL_PREVIOUS_CONTENT="$(cat "$PREVIOUS_FILE")"
fi
readonly ORIGINAL_PREVIOUS_EXISTS ORIGINAL_PREVIOUS_CONTENT

IMAGE_TAG="$TARGET_TAG"
export IMAGE_TAG

if ! existing_services="$(compose ps --all --services backend frontend)"; then
  echo "failed to inspect the existing application services" >&2
  exit 7
fi
if [[ "$HAS_PREVIOUS" == false ]] && grep -Eqx '(backend|frontend)' <<<"$existing_services"; then
  echo "existing backend or frontend has no valid current SHA; establish deploy/current-version before deploying" >&2
  exit 6
fi

DEPLOY_STARTED=false
BACKEND_STARTED=false
FRONTEND_STARTED=false
BACKUP_DIR=""

rollback() {
  [[ "$HAS_PREVIOUS" == true ]] || return 1

  echo "rolling back images to $PREVIOUS_TAG" >&2
  IMAGE_TAG="$PREVIOUS_TAG"
  export IMAGE_TAG
  compose up -d --pull never backend || return 1
  wait_version_json "http://127.0.0.1:8000/health" "$PREVIOUS_TAG" true || return 1
  compose up -d --pull never frontend || return 1
  verify_runtime_version "$PREVIOUS_TAG" || return 1
  restore_version_state || return 1
}

restore_file_snapshot() {
  local existed="$1"
  local content="$2"
  local destination="$3"

  if [[ "$existed" == true ]]; then
    atomic_write "$content" "$destination"
  else
    rm -f "$destination"
  fi
}

restore_version_state() {
  restore_file_snapshot "$ORIGINAL_PREVIOUS_EXISTS" "$ORIGINAL_PREVIOUS_CONTENT" "$PREVIOUS_FILE" || return 1
  restore_file_snapshot "$ORIGINAL_CURRENT_EXISTS" "$ORIGINAL_CURRENT_CONTENT" "$CURRENT_FILE"
}

cleanup_first_deploy() {
  local cleanup_failed=false

  if [[ "$FRONTEND_STARTED" == true ]]; then
    compose stop frontend || cleanup_failed=true
  fi
  if [[ "$BACKEND_STARTED" == true ]]; then
    compose stop backend || cleanup_failed=true
  fi
  if [[ "$cleanup_failed" == false ]]; then
    restore_version_state
  else
    return 1
  fi
}

recover_images() {
  if [[ "$HAS_PREVIOUS" == true ]]; then
    rollback
  else
    cleanup_first_deploy
  fi
}

validate_backup_dir() {
  local path="$1"
  local prefix="$BACKUPS_DIR/"
  local name
  [[ "$path" == "$prefix"* ]] || return 1
  name="${path#"$prefix"}"
  [[ "$name" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{40}\.[A-Za-z0-9]+$ ]]
}

cleanup_partial_backup() {
  [[ -n "$BACKUP_DIR" ]] || return 0
  validate_backup_dir "$BACKUP_DIR" || return 1
  [[ ! -e "$BACKUP_DIR" ]] && return 0
  [[ -d "$BACKUP_DIR" && ! -L "$BACKUP_DIR" ]] || return 1
  rm -f -- "$BACKUP_DIR/data.tar.gz.partial"
  rmdir -- "$BACKUP_DIR" 2>/dev/null || true
}

disable_failure_traps() {
  trap - ERR HUP INT TERM
}

on_error() {
  local original_exit_code="$?"
  local recovery_ok=true
  local cleanup_ok=true
  disable_failure_traps

  if [[ "$DEPLOY_STARTED" == true ]]; then
    if ! recover_images; then
      recovery_ok=false
      echo "automatic image recovery failed; run $DEPLOY_ROOT/scripts/recover-interrupted.sh" >&2
    fi
  fi
  cleanup_partial_backup || cleanup_ok=false
  [[ "$cleanup_ok" == true ]] ||
    echo "partial backup cleanup failed; transaction marker retained" >&2
  if [[ "$recovery_ok" == true && "$cleanup_ok" == true ]]; then
    rm -f -- "$TRANSACTION_FILE"
  fi

  exit "$original_exit_code"
}

on_signal() {
  local signal_exit_code="$1"
  local recovery_ok=true
  local cleanup_ok=true
  disable_failure_traps

  if [[ "$DEPLOY_STARTED" == true ]]; then
    if ! recover_images; then
      recovery_ok=false
      echo "automatic image recovery failed after signal; run $DEPLOY_ROOT/scripts/recover-interrupted.sh" >&2
    fi
  fi
  cleanup_partial_backup || cleanup_ok=false
  [[ "$cleanup_ok" == true ]] ||
    echo "partial backup cleanup failed after signal; transaction marker retained" >&2
  if [[ "$recovery_ok" == true && "$cleanup_ok" == true ]]; then
    rm -f -- "$TRANSACTION_FILE"
  fi

  exit "$signal_exit_code"
}

trap on_error ERR
trap 'on_signal 129' HUP
trap 'on_signal 130' INT
trap 'on_signal 143' TERM

echo "pulling target image tag $TARGET_TAG"
compose pull backend frontend
if [[ "$HAS_PREVIOUS" == true ]]; then
  echo "ensuring rollback image tag $PREVIOUS_TAG is available"
  IMAGE_TAG="$PREVIOUS_TAG"
  export IMAGE_TAG
  compose pull backend frontend
  IMAGE_TAG="$TARGET_TAG"
  export IMAGE_TAG
fi

original_previous_tag="none"
if [[ "$ORIGINAL_PREVIOUS_EXISTS" == true ]]; then
  original_previous_tag="$(printf '%s' "$ORIGINAL_PREVIOUS_CONTENT" | tr -d '[:space:]')"
  [[ "$original_previous_tag" =~ ^[0-9a-f]{40}$ ]] || production_preflight_invalid_app "deploy/previous-version is invalid"
fi

if ! read -r DATA_SIZE_KIB _ < <(du -sk -- "$DATA_DIR"); then
  echo "failed to measure current data size" >&2
  exit 7
fi
if [[ ! "$DATA_SIZE_KIB" =~ ^[0-9]+$ ]]; then
  echo "invalid data size reported by du" >&2
  exit 7
fi
if ! AVAILABLE_KIB="$(df -Pk -- "$BACKUPS_DIR" | awk 'NR > 1 { available = $4 } END { print available }')"; then
  echo "failed to measure backup filesystem free space" >&2
  exit 7
fi
if [[ ! "$AVAILABLE_KIB" =~ ^[0-9]+$ ]]; then
  echo "invalid free space reported by df" >&2
  exit 7
fi
RESERVE_KIB=$(( (DISK_RESERVE_BYTES + 1023) / 1024 ))
REQUIRED_KIB=$(( DATA_SIZE_KIB + RESERVE_KIB ))
if (( AVAILABLE_KIB < REQUIRED_KIB )); then
  echo "insufficient free space for backup: need ${REQUIRED_KIB} KiB, have ${AVAILABLE_KIB} KiB" >&2
  exit 7
fi
readonly DATA_SIZE_KIB AVAILABLE_KIB RESERVE_KIB REQUIRED_KIB

if ! BACKUP_DIR="$(mktemp -d "$BACKUPS_DIR/$(date -u +%Y%m%dT%H%M%SZ)-$TARGET_TAG.XXXXXX")"; then
  echo "failed to create the deployment backup directory" >&2
  false
fi

transaction_previous_tag="${PREVIOUS_TAG:-none}"
atomic_write "version=1
operation=deploy
phase=runtime
target_tag=$TARGET_TAG
previous_tag=$transaction_previous_tag
original_previous_tag=$original_previous_tag
backup_dir=$BACKUP_DIR" "$TRANSACTION_FILE"

DEPLOY_STARTED=true
compose stop backend
if ! backend_states="$(compose ps --all --format '{{.State}}' backend)"; then
  echo "failed to confirm that the backend stopped" >&2
  false
fi
if [[ -n "$backend_states" ]] && grep -Evqx '(exited|dead)' <<<"$backend_states"; then
  echo "backend did not stop; observed states: $backend_states" >&2
  false
fi

PARTIAL_ARCHIVE="$BACKUP_DIR/data.tar.gz.partial"
if ! tar -C "$DATA_DIR" -czf "$PARTIAL_ARCHIVE" .; then
  false
fi
mv -- "$PARTIAL_ARCHIVE" "$BACKUP_DIR/data.tar.gz"
printf '%s\n' "$PREVIOUS_TAG" > "$BACKUP_DIR/previous-image-tag"

IMAGE_TAG="$TARGET_TAG"
export IMAGE_TAG
BACKEND_STARTED=true
compose up -d --pull never backend
wait_version_json "http://127.0.0.1:8000/health" "$TARGET_TAG" true

FRONTEND_STARTED=true
compose up -d --pull never frontend
verify_runtime_version "$TARGET_TAG"

if [[ "$ALLOW_REDEPLOY" == true && "$TARGET_TAG" == "$PREVIOUS_TAG" ]]; then
  restore_file_snapshot "$ORIGINAL_PREVIOUS_EXISTS" "$ORIGINAL_PREVIOUS_CONTENT" "$PREVIOUS_FILE"
elif [[ "$HAS_PREVIOUS" == true ]]; then
  atomic_write "$PREVIOUS_TAG" "$PREVIOUS_FILE"
else
  rm -f "$PREVIOUS_FILE"
fi
atomic_write "$TARGET_TAG" "$CURRENT_FILE"

DEPLOY_STARTED=false
rm -f -- "$TRANSACTION_FILE"
disable_failure_traps
echo "deployment succeeded: $TARGET_TAG"
