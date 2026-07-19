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

for command_name in docker curl tar flock mktemp du df awk; do
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

[[ "$seen_registry" == true && "$ACR_REGISTRY" =~ ^[a-z0-9][a-z0-9-]*-registry\.cn-beijing\.cr\.aliyuncs\.com$ ]] ||
  invalid_deploy_env "ACR_REGISTRY must be a Beijing ACR Enterprise Edition public endpoint"
[[ "$ACR_REGISTRY" != "your-instance-registry.cn-beijing.cr.aliyuncs.com" ]] ||
  invalid_deploy_env "ACR_REGISTRY still contains the Enterprise Edition example placeholder"
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
if [[ -e "$TRANSACTION_FILE" ]]; then
  echo "an interrupted transaction exists; run $DEPLOY_ROOT/scripts/recover-interrupted.sh" >&2
  exit 5
fi

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
  first_character="${value:0:1}"
  last_character="${value: -1}"
  if [[ "$first_character" == \" || "$first_character" == "'" ||
    "$last_character" == \" || "$last_character" == "'" ]]; then
    invalid_app_env "quoted values are not allowed for $key; Compose raw env values must be exact"
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
[[ "${SESSION_COOKIE_SECURE_VALUE,,}" == true ]] || invalid_app_env "SESSION_COOKIE_SECURE must be true"
[[ -n "$ADMIN_EMAILS_VALUE" ]] || invalid_app_env "ADMIN_EMAILS is required"
[[ "${ADMIN_EMAILS_VALUE,,}" != *"admin@example"* && "${ADMIN_EMAILS_VALUE,,}" != *"@example."* ]] ||
  invalid_app_env "ADMIN_EMAILS must not use an example administrator"
[[ "$APP_ENCRYPTION_KEY_VALUE" =~ ^[A-Za-z0-9_-]{43}=$ ]] ||
  invalid_app_env "APP_ENCRYPTION_KEY must be a 44-character URL-safe base64 Fernet key"

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
  [[ "$original_previous_tag" =~ ^[0-9a-f]{40}$ ]] || invalid_app_env "deploy/previous-version is invalid"
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
rm -f -- "$TRANSACTION_FILE"
disable_failure_traps
echo "deployment succeeded: $TARGET_TAG"
