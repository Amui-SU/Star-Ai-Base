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

invalid_app_env() {
  echo "invalid production application environment: $1" >&2
  exit 6
}

DEBUG_VALUE=""
SESSION_COOKIE_SECURE_VALUE=""
ADMIN_EMAILS_VALUE=""
APP_ENCRYPTION_KEY_VALUE=""
SMTP_HOST_VALUE=""
SMTP_USER_VALUE=""
SMTP_PASSWORD_VALUE=""
SMTP_FROM_VALUE=""
GOOGLE_CLIENT_ID_VALUE=""
GOOGLE_CLIENT_SECRET_VALUE=""
GOOGLE_REDIRECT_URI_VALUE=""
declare -A seen_app_keys=()

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  [[ "$line" == *=* ]] || invalid_app_env "expected KEY=VALUE"

  key="${line%%=*}"
  value="${line#*=}"
  [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || invalid_app_env "invalid key: $key"
  if (( ${#value} >= 2 )); then
    first_character="${value:0:1}"
    last_character="${value: -1}"
    if [[ "$first_character" == \" || "$first_character" == "'" ]]; then
      [[ "$last_character" == "$first_character" ]] || invalid_app_env "unmatched quote for $key"
      value="${value:1:${#value}-2}"
    fi
  fi
  [[ "$value" != REPLACE_* ]] || invalid_app_env "placeholder remains for $key"

  case "$key" in
    DEBUG|SESSION_COOKIE_SECURE|ADMIN_EMAILS|APP_ENCRYPTION_KEY|SMTP_HOST|SMTP_USER|SMTP_PASSWORD|SMTP_FROM|GOOGLE_CLIENT_ID|GOOGLE_CLIENT_SECRET|GOOGLE_REDIRECT_URI)
      [[ -z "${seen_app_keys[$key]+x}" ]] || invalid_app_env "duplicate key: $key"
      seen_app_keys[$key]=true
      ;;
  esac

  case "$key" in
    DEBUG) DEBUG_VALUE="$value" ;;
    SESSION_COOKIE_SECURE) SESSION_COOKIE_SECURE_VALUE="$value" ;;
    ADMIN_EMAILS) ADMIN_EMAILS_VALUE="$value" ;;
    APP_ENCRYPTION_KEY) APP_ENCRYPTION_KEY_VALUE="$value" ;;
    SMTP_HOST) SMTP_HOST_VALUE="$value" ;;
    SMTP_USER) SMTP_USER_VALUE="$value" ;;
    SMTP_PASSWORD) SMTP_PASSWORD_VALUE="$value" ;;
    SMTP_FROM) SMTP_FROM_VALUE="$value" ;;
    GOOGLE_CLIENT_ID) GOOGLE_CLIENT_ID_VALUE="$value" ;;
    GOOGLE_CLIENT_SECRET) GOOGLE_CLIENT_SECRET_VALUE="$value" ;;
    GOOGLE_REDIRECT_URI) GOOGLE_REDIRECT_URI_VALUE="$value" ;;
  esac
done < "$APP_ENV"

[[ "$DEBUG_VALUE" == false ]] || invalid_app_env "DEBUG must be false"
[[ "${SESSION_COOKIE_SECURE_VALUE,,}" != false ]] || invalid_app_env "SESSION_COOKIE_SECURE must not be false"
[[ -n "$ADMIN_EMAILS_VALUE" ]] || invalid_app_env "ADMIN_EMAILS is required"
[[ "${ADMIN_EMAILS_VALUE,,}" != *"admin@example"* && "${ADMIN_EMAILS_VALUE,,}" != *"@example."* ]] ||
  invalid_app_env "ADMIN_EMAILS must not use an example administrator"
(( ${#APP_ENCRYPTION_KEY_VALUE} >= 32 )) || invalid_app_env "APP_ENCRYPTION_KEY must be at least 32 characters"

smtp_any=false
smtp_complete=false
if [[ -n "$SMTP_HOST_VALUE" || -n "$SMTP_USER_VALUE" || -n "$SMTP_PASSWORD_VALUE" || -n "$SMTP_FROM_VALUE" ]]; then
  smtp_any=true
  if [[ -n "$SMTP_HOST_VALUE" && -n "$SMTP_USER_VALUE" && -n "$SMTP_PASSWORD_VALUE" && -n "$SMTP_FROM_VALUE" ]]; then
    smtp_complete=true
  else
    invalid_app_env "SMTP login is partial; configure HOST, USER, PASSWORD, and FROM"
  fi
fi

google_any=false
google_complete=false
if [[ -n "$GOOGLE_CLIENT_ID_VALUE" || -n "$GOOGLE_CLIENT_SECRET_VALUE" ]]; then
  google_any=true
  if [[ -n "$GOOGLE_CLIENT_ID_VALUE" && -n "$GOOGLE_CLIENT_SECRET_VALUE" ]]; then
    [[ "$GOOGLE_REDIRECT_URI_VALUE" == "https://zhiku-cloud.cn/system-auth/google/callback" ]] ||
      invalid_app_env "GOOGLE_REDIRECT_URI must use the canonical HTTPS callback"
    google_complete=true
  else
    invalid_app_env "Google login is partial; configure both client ID and secret"
  fi
fi

[[ "$smtp_any" == false || "$smtp_complete" == true ]] || invalid_app_env "SMTP login is incomplete"
[[ "$google_any" == false || "$google_complete" == true ]] || invalid_app_env "Google login is incomplete"
[[ "$smtp_complete" == true || "$google_complete" == true ]] || invalid_app_env "at least one usable login method is required"

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

ORIGINAL_CURRENT_EXISTS=false
ORIGINAL_CURRENT_CONTENT=""
if [[ -f "$CURRENT_FILE" ]]; then
  ORIGINAL_CURRENT_EXISTS=true
  ORIGINAL_CURRENT_CONTENT="$(cat "$CURRENT_FILE")"
fi
readonly ORIGINAL_CURRENT_EXISTS ORIGINAL_CURRENT_CONTENT

ORIGINAL_PREVIOUS_EXISTS=false
ORIGINAL_PREVIOUS_CONTENT=""
if [[ -f "$PREVIOUS_FILE" ]]; then
  ORIGINAL_PREVIOUS_EXISTS=true
  ORIGINAL_PREVIOUS_CONTENT="$(cat "$PREVIOUS_FILE")"
fi
readonly ORIGINAL_PREVIOUS_EXISTS ORIGINAL_PREVIOUS_CONTENT

PREVIOUS_TAG="$(printf '%s' "$ORIGINAL_CURRENT_CONTENT" | tr -d '[:space:]')"
if [[ "$PREVIOUS_TAG" =~ ^[0-9a-f]{40}$ ]]; then
  readonly HAS_PREVIOUS=true
else
  PREVIOUS_TAG=""
  readonly HAS_PREVIOUS=false
fi
readonly PREVIOUS_TAG

IMAGE_TAG="$TARGET_TAG"
export IMAGE_TAG

if ! existing_backend="$(compose ps --all --services backend)"; then
  echo "failed to inspect the existing backend service" >&2
  exit 7
fi
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

disable_failure_traps() {
  trap - ERR HUP INT TERM
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

if ! BACKUP_DIR="$(mktemp -d "$BACKUPS_DIR/$(date -u +%Y%m%dT%H%M%SZ)-$TARGET_TAG.XXXXXX")"; then
  echo "failed to create the deployment backup directory" >&2
  false
fi
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
