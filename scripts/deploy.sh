#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if (( $# != 1 )) || [[ ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "usage: $0 <40-character-git-sha>" >&2
  exit 2
fi
readonly TARGET_TAG="$1"

readonly DEPLOY_ROOT="${ZHIKU_DEPLOY_ROOT:-/opt/zhiku-cloud}"
readonly COMPOSE_FILE="$DEPLOY_ROOT/compose.production.yml"
readonly DEPLOY_DIR="$DEPLOY_ROOT/deploy"
readonly DEPLOY_ENV="$DEPLOY_DIR/.env.deploy"
readonly APP_ENV="$DEPLOY_DIR/.env.production"
readonly DATA_DIR="$DEPLOY_ROOT/data"
readonly LOG_DIR="$DEPLOY_ROOT/logs"
readonly BACKUPS_DIR="$DEPLOY_ROOT/backups"
readonly CURRENT_FILE="$DEPLOY_DIR/current-version"
readonly PREVIOUS_FILE="$DEPLOY_DIR/previous-version"
readonly HTTP_ATTEMPTS="${ZHIKU_DEPLOY_HTTP_ATTEMPTS:-30}"
readonly HTTP_DELAY_SECONDS="${ZHIKU_DEPLOY_HTTP_DELAY_SECONDS:-2}"

if [[ ! "$HTTP_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] || [[ ! "$HTTP_DELAY_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "invalid deployment health retry configuration" >&2
  exit 2
fi

for command_name in docker curl tar flock mktemp; do
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

invalid_deploy_env() {
  echo "invalid deployment environment: $1" >&2
  exit 4
}

ACR_REGISTRY=""
ACR_NAMESPACE=""
PUBLIC_BASE_URL=""
seen_registry=false
seen_namespace=false
seen_public_url=false

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  [[ "$line" == *=* ]] || invalid_deploy_env "expected KEY=VALUE"

  key="${line%%=*}"
  value="${line#*=}"
  case "$key" in
    ACR_REGISTRY)
      [[ "$seen_registry" == false ]] || invalid_deploy_env "duplicate ACR_REGISTRY"
      ACR_REGISTRY="$value"
      seen_registry=true
      ;;
    ACR_NAMESPACE)
      [[ "$seen_namespace" == false ]] || invalid_deploy_env "duplicate ACR_NAMESPACE"
      ACR_NAMESPACE="$value"
      seen_namespace=true
      ;;
    PUBLIC_BASE_URL)
      [[ "$seen_public_url" == false ]] || invalid_deploy_env "duplicate PUBLIC_BASE_URL"
      PUBLIC_BASE_URL="$value"
      seen_public_url=true
      ;;
    *)
      invalid_deploy_env "unknown key: $key"
      ;;
  esac
done < "$DEPLOY_ENV"

[[ "$seen_registry" == true && "$ACR_REGISTRY" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*(:[0-9]+)?$ ]] ||
  invalid_deploy_env "ACR_REGISTRY has an unsafe value"
[[ "$seen_namespace" == true && "$ACR_NAMESPACE" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]] ||
  invalid_deploy_env "ACR_NAMESPACE has an unsafe value"
[[ "$seen_public_url" == true ]] || invalid_deploy_env "PUBLIC_BASE_URL is required"
[[ "$PUBLIC_BASE_URL" =~ ^https://[A-Za-z0-9][A-Za-z0-9.-]*(:[0-9]+)?(/[^[:space:]?#]*)?$ ]] ||
  invalid_deploy_env "PUBLIC_BASE_URL must be a valid HTTPS URL without credentials, query, or fragment"

readonly ACR_REGISTRY ACR_NAMESPACE PUBLIC_BASE_URL
export ACR_REGISTRY ACR_NAMESPACE

mkdir -p "$DEPLOY_DIR" "$DATA_DIR" "$LOG_DIR" "$BACKUPS_DIR"
exec 9>"$DEPLOY_DIR/deploy.lock"
if ! flock -n 9; then
  echo "another deployment is already in progress" >&2
  exit 5
fi

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

PREVIOUS_TAG=""
if [[ -f "$CURRENT_FILE" ]]; then
  PREVIOUS_TAG="$(tr -d '[:space:]' < "$CURRENT_FILE")"
fi
if [[ "$PREVIOUS_TAG" =~ ^[0-9a-f]{40}$ ]]; then
  readonly HAS_PREVIOUS=true
else
  PREVIOUS_TAG=""
  readonly HAS_PREVIOUS=false
fi
readonly PREVIOUS_TAG

IMAGE_TAG="$TARGET_TAG"
export IMAGE_TAG

existing_backend="$(compose ps --all --services backend)"
if [[ "$HAS_PREVIOUS" == false ]] && grep -Fxq backend <<<"$existing_backend"; then
  echo "existing backend has no valid current SHA; establish deploy/current-version before deploying" >&2
  exit 6
fi

DEPLOY_STARTED=false
BACKEND_STARTED=false
FRONTEND_STARTED=false

rollback() {
  [[ "$HAS_PREVIOUS" == true ]] || return 1

  echo "rolling back images to $PREVIOUS_TAG" >&2
  IMAGE_TAG="$PREVIOUS_TAG"
  export IMAGE_TAG
  compose up -d --pull never backend || return 1
  wait_http "http://127.0.0.1:8000/health" "$HTTP_ATTEMPTS" "$HTTP_DELAY_SECONDS" '{"status":"healthy"}' || return 1
  compose up -d --pull never frontend || return 1
  wait_http "http://127.0.0.1:3000/" || return 1
  wait_http "${PUBLIC_BASE_URL%/}/" || return 1
  wait_http "${PUBLIC_BASE_URL%/}/health" "$HTTP_ATTEMPTS" "$HTTP_DELAY_SECONDS" '{"status":"healthy"}' || return 1
}

cleanup_first_deploy() {
  local cleanup_failed=false

  if [[ "$FRONTEND_STARTED" == true ]]; then
    compose stop frontend || cleanup_failed=true
  fi
  if [[ "$BACKEND_STARTED" == true ]]; then
    compose stop backend || cleanup_failed=true
  fi
  [[ "$cleanup_failed" == false ]]
}

recover_images() {
  if [[ "$HAS_PREVIOUS" == true ]]; then
    rollback
  else
    cleanup_first_deploy
  fi
}

disable_failure_traps() {
  trap - ERR INT TERM
}

on_error() {
  local original_exit_code="$?"
  disable_failure_traps

  if [[ "$DEPLOY_STARTED" == true ]]; then
    recover_images || echo "automatic image recovery failed; inspect docker compose logs" >&2
  fi

  exit "$original_exit_code"
}

on_signal() {
  local signal_exit_code="$1"
  disable_failure_traps

  if [[ "$DEPLOY_STARTED" == true ]]; then
    recover_images || echo "automatic image recovery failed after signal; inspect docker compose logs" >&2
  fi

  exit "$signal_exit_code"
}

trap on_error ERR
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

DEPLOY_STARTED=true
compose stop backend
backend_states="$(compose ps --all --format '{{.State}}' backend)"
if [[ -n "$backend_states" ]] && grep -Evqx '(exited|dead)' <<<"$backend_states"; then
  echo "backend did not stop; observed states: $backend_states" >&2
  false
fi

BACKUP_DIR="$(mktemp -d "$BACKUPS_DIR/$(date -u +%Y%m%dT%H%M%SZ)-$TARGET_TAG.XXXXXX")"
readonly BACKUP_DIR
tar -C "$DATA_DIR" -czf "$BACKUP_DIR/data.tar.gz" .
printf '%s\n' "$PREVIOUS_TAG" > "$BACKUP_DIR/previous-image-tag"

IMAGE_TAG="$TARGET_TAG"
export IMAGE_TAG
BACKEND_STARTED=true
compose up -d --pull never backend
wait_http "http://127.0.0.1:8000/health" "$HTTP_ATTEMPTS" "$HTTP_DELAY_SECONDS" '{"status":"healthy"}'

FRONTEND_STARTED=true
compose up -d --pull never frontend
wait_http "http://127.0.0.1:3000/"
wait_http "${PUBLIC_BASE_URL%/}/"
wait_http "${PUBLIC_BASE_URL%/}/health" "$HTTP_ATTEMPTS" "$HTTP_DELAY_SECONDS" '{"status":"healthy"}'

if [[ "$HAS_PREVIOUS" == true ]]; then
  atomic_write "$PREVIOUS_TAG" "$PREVIOUS_FILE"
else
  rm -f "$PREVIOUS_FILE"
fi
atomic_write "$TARGET_TAG" "$CURRENT_FILE"

DEPLOY_STARTED=false
disable_failure_traps
echo "deployment succeeded: $TARGET_TAG"
