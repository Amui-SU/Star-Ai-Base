#!/usr/bin/env bash
set -Eeuo pipefail

if (( $# != 1 )) || [[ ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "usage: $0 <40-character-git-sha>" >&2
  exit 2
fi
TARGET_TAG="$1"

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

IMAGE_TAG="$TARGET_TAG"
export ACR_REGISTRY ACR_NAMESPACE IMAGE_TAG

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
    if (( attempt < attempts )); then
      sleep "$delay_seconds"
    fi
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
    echo "no valid previous image tag is available for automatic rollback" >&2
    return 1
  fi

  echo "rolling back images to $PREVIOUS_TAG" >&2
  IMAGE_TAG="$PREVIOUS_TAG"
  export IMAGE_TAG
  compose up -d backend || return 1
  wait_http "http://127.0.0.1:8000/health" || return 1
  compose up -d frontend || return 1
  wait_http "http://127.0.0.1:3000/" || return 1
  wait_http "${PUBLIC_BASE_URL%/}/health" || return 1
}

on_error() {
  local original_exit_code="$?"
  trap - ERR

  if [[ "$DEPLOY_STARTED" == true ]]; then
    rollback || echo "automatic image rollback failed; inspect docker compose logs" >&2
  fi

  exit "$original_exit_code"
}
trap on_error ERR

echo "pulling image tag $TARGET_TAG"
compose pull backend frontend

RUNNING_SERVICES="$(compose ps --status running --services)"
if grep -Fxq backend <<<"$RUNNING_SERVICES"; then
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
