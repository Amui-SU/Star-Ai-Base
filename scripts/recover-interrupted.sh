#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

readonly DEPLOY_ROOT="${ZHIKU_DEPLOY_ROOT:-/opt/zhiku-cloud}"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly PRODUCTION_PREFLIGHT="$SCRIPT_DIR/production-preflight.sh"
readonly RUNTIME_ATTESTATION="$SCRIPT_DIR/runtime-attestation.sh"
readonly COMPOSE_FILE="$DEPLOY_ROOT/compose.production.yml"
readonly DEPLOY_DIR="$DEPLOY_ROOT/deploy"
readonly DEPLOY_ENV="$DEPLOY_DIR/.env.deploy"
readonly APP_ENV="$DEPLOY_DIR/.env.production"
readonly DATA_DIR="$DEPLOY_ROOT/data"
readonly CURRENT_FILE="$DEPLOY_DIR/current-version"
readonly PREVIOUS_FILE="$DEPLOY_DIR/previous-version"
readonly TRANSACTION_FILE="$DEPLOY_DIR/transaction"
readonly HTTP_ATTEMPTS="${ZHIKU_RECOVER_HTTP_ATTEMPTS:-30}"
readonly HTTP_DELAY_SECONDS="${ZHIKU_RECOVER_HTTP_DELAY_SECONDS:-2}"

for command_name in docker curl flock mktemp mv rm rmdir grep tr sleep python3; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "missing required command: $command_name" >&2
    exit 3
  }
done
for required_file in "$PRODUCTION_PREFLIGHT" "$RUNTIME_ATTESTATION" "$COMPOSE_FILE" "$DEPLOY_ENV" "$APP_ENV" "$TRANSACTION_FILE"; do
  [[ -f "$required_file" ]] || {
    echo "missing required recovery file: $required_file" >&2
    exit 4
  }
done
[[ "$HTTP_ATTEMPTS" =~ ^[1-9][0-9]*$ && "$HTTP_DELAY_SECONDS" =~ ^[0-9]+$ ]] || {
  echo "invalid recovery health retry configuration" >&2
  exit 2
}

exec 9>"$DEPLOY_DIR/deploy.lock"
if ! flock -n 9; then
  echo "another deployment or restore is already in progress" >&2
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

declare -A marker=()
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ "$line" == *=* ]] || {
    echo "invalid transaction marker line" >&2
    exit 6
  }
  key="${line%%=*}"
  value="${line#*=}"
  [[ "$key" =~ ^[a-z_]+$ && -z "${marker[$key]+x}" ]] || {
    echo "invalid or duplicate transaction marker key: $key" >&2
    exit 6
  }
  marker[$key]="$value"
done < "$TRANSACTION_FILE"

[[ "${marker[version]:-}" == 1 ]] || {
  echo "unsupported transaction marker version" >&2
  exit 6
}

case "${marker[operation]:-}" in
  restore)
    [[ "${#marker[@]}" == 6 ]] || {
      echo "restore transaction marker has unexpected keys" >&2
      exit 6
    }
    [[ "${marker[phase]:-}" =~ ^(prepared|old_moved|new_active|rollback_started|rollback_ready)$ ]] || {
      echo "invalid restore transaction phase" >&2
      exit 6
    }
    ;;
  deploy)
    [[ "${#marker[@]}" == 7 ]] || {
      echo "deploy transaction marker has unexpected keys" >&2
      exit 6
    }
    [[ "${marker[phase]:-}" == runtime ]] || {
      echo "invalid deploy transaction phase" >&2
      exit 6
    }
    [[ "${marker[target_tag]:-}" =~ ^[0-9a-f]{40}$ ]] || {
      echo "invalid deploy target tag" >&2
      exit 6
    }
    ;;
  *)
    echo "transaction marker must declare operation=deploy or operation=restore" >&2
    exit 6
    ;;
esac

# shellcheck source=production-preflight.sh
source "$PRODUCTION_PREFLIGHT"
production_preflight "$DEPLOY_ENV" "$APP_ENV"
readonly ACR_REGISTRY ACR_NAMESPACE PUBLIC_BASE_URL

compose() {
  docker compose \
    --project-name zhiku-cloud \
    --project-directory "$DEPLOY_ROOT" \
    --env-file "$DEPLOY_ENV" \
    -f "$COMPOSE_FILE" \
    "$@"
}

# shellcheck source=runtime-attestation.sh
source "$RUNTIME_ATTESTATION"

atomic_write() {
  local value="$1"
  local destination="$2"
  local temporary
  temporary="$(mktemp "${destination}.tmp.XXXXXX")" || return 1
  if ! printf '%s\n' "$value" > "$temporary" || ! mv -- "$temporary" "$destination"; then
    rm -f -- "$temporary"
    return 1
  fi
}

write_restore_marker_phase() {
  local phase="$1"
  atomic_write "version=1
operation=restore
phase=$phase
current_tag=${marker[current_tag]}
staged_data=${marker[staged_data]}
safety_parent=${marker[safety_parent]}" "$TRANSACTION_FILE" || return 1
  marker[phase]="$phase"
}

validate_tag_or_none() {
  [[ "$1" == none || "$1" =~ ^[0-9a-f]{40}$ ]]
}

validate_runtime_path() {
  local path="$1"
  local prefix="$2"
  local expected_prefix="$DEPLOY_ROOT/$prefix."
  local suffix
  [[ "$path" == "$expected_prefix"* ]] || return 1
  suffix="${path#"$expected_prefix"}"
  [[ "$suffix" =~ ^[A-Za-z0-9]+$ ]]
}

validate_backup_dir() {
  local path="$1"
  local prefix="$DEPLOY_ROOT/backups/"
  local name
  [[ "$path" == "$prefix"* ]] || return 1
  name="${path#"$prefix"}"
  [[ "$name" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{40}\.[A-Za-z0-9]+$ ]]
}

cleanup_partial_backup() {
  local path="$1"
  validate_backup_dir "$path" || return 1
  [[ ! -e "$path" ]] && return 0
  [[ -d "$path" && ! -L "$path" ]] || return 1
  rm -f -- "$path/data.tar.gz.partial"
  rmdir -- "$path" 2>/dev/null || true
}

safe_remove_staging() {
  local path="$1"
  validate_runtime_path "$path" data.restore || return 1
  [[ ! -L "$path" ]] || return 1
  rm -rf -- "$path"
}

manual_failure() {
  compose stop backend >/dev/null 2>&1 || true
  echo "automatic reconciliation failed; backend left stopped" >&2
  echo "active data path: $DATA_DIR" >&2
  [[ -n "${marker[safety_parent]:-}" ]] &&
    echo "old data path: ${marker[safety_parent]}/data" >&2
  [[ -n "${marker[staged_data]:-}" ]] &&
    echo "staged data path: ${marker[staged_data]}" >&2
  [[ -n "${marker[backup_dir]:-}" ]] &&
    echo "deployment backup path: ${marker[backup_dir]}" >&2
  echo "transaction marker retained: $TRANSACTION_FILE" >&2
  exit 8
}

recover_restore() {
  local current_tag="${marker[current_tag]:-}"
  local staged_data="${marker[staged_data]:-}"
  local safety_parent="${marker[safety_parent]:-}"
  local phase="${marker[phase]}"

  [[ "$current_tag" =~ ^[0-9a-f]{40}$ ]] || {
    echo "invalid restore current tag; transaction marker retained" >&2
    exit 6
  }
  validate_runtime_path "$staged_data" data.restore || {
    echo "invalid restore staging path; transaction marker retained" >&2
    exit 6
  }
  validate_runtime_path "$safety_parent" data.safety || {
    echo "invalid restore safety path; transaction marker retained" >&2
    exit 6
  }

  IMAGE_TAG="$current_tag"
  export IMAGE_TAG
  compose stop backend || manual_failure

  case "$phase" in
    prepared)
      if [[ -d "$DATA_DIR" && -d "$staged_data" && ! -e "$safety_parent/data" && ! -e "$safety_parent/failed-restored-data" ]]; then
        : # The original data is still active before the first rename.
      elif [[ ! -e "$DATA_DIR" && -d "$staged_data" && -d "$safety_parent/data" && ! -e "$safety_parent/failed-restored-data" ]]; then
        : # The first rename completed before its phase update.
      else
        manual_failure
      fi
      ;;
    old_moved)
      if [[ ! -e "$DATA_DIR" && -d "$staged_data" && -d "$safety_parent/data" && ! -e "$safety_parent/failed-restored-data" ]]; then
        : # The original data is preserved and the replacement is still staged.
      elif [[ -d "$DATA_DIR" && ! -e "$staged_data" && -d "$safety_parent/data" && ! -e "$safety_parent/failed-restored-data" ]]; then
        : # The replacement became active before its phase update.
      else
        manual_failure
      fi
      ;;
    new_active)
      [[ -d "$DATA_DIR" && ! -e "$staged_data" && -d "$safety_parent/data" && ! -e "$safety_parent/failed-restored-data" ]] || manual_failure
      ;;
    rollback_started)
      if [[ -d "$safety_parent/data" ]]; then
        [[ ! -e "$safety_parent/failed-restored-data" || ! -e "$DATA_DIR" ]] || manual_failure
      elif [[ -d "$DATA_DIR" && -d "$staged_data" && ! -e "$safety_parent/failed-restored-data" ]]; then
        : # Pre-swap rollback was recorded before staging cleanup.
      elif [[ -d "$DATA_DIR" && ! -e "$staged_data" && -d "$safety_parent/failed-restored-data" ]]; then
        : # The original data rename completed before the ready phase update.
      else
        manual_failure
      fi
      ;;
    rollback_ready)
      [[ -d "$DATA_DIR" && ! -e "$safety_parent/data" ]] || manual_failure
      ;;
  esac

  if [[ "$phase" != rollback_ready ]]; then
    write_restore_marker_phase rollback_started || manual_failure
    if [[ -d "$safety_parent/data" ]]; then
      if [[ -e "$DATA_DIR" ]]; then
        [[ ! -e "$safety_parent/failed-restored-data" ]] || manual_failure
        mv -- "$DATA_DIR" "$safety_parent/failed-restored-data" || manual_failure
      fi
      mv -- "$safety_parent/data" "$DATA_DIR" || manual_failure
    elif [[ -d "$DATA_DIR" && -d "$staged_data" && ! -e "$safety_parent/failed-restored-data" ]]; then
      : # The original data was never moved.
    elif [[ -d "$DATA_DIR" && ! -e "$staged_data" && -d "$safety_parent/failed-restored-data" ]]; then
      : # Rollback completed before the ready phase update.
    else
      manual_failure
    fi
    [[ -d "$DATA_DIR" && ! -e "$safety_parent/data" ]] || manual_failure
    write_restore_marker_phase rollback_ready || manual_failure
  fi

  if [[ -d "$staged_data" ]]; then
    safe_remove_staging "$staged_data" || manual_failure
  fi
  [[ ! -e "$staged_data" ]] || manual_failure

  compose up -d --pull never backend || manual_failure
  wait_version_json "http://127.0.0.1:8000/health" "$current_tag" true || manual_failure
  wait_version_json "${PUBLIC_BASE_URL%/}/health" "$current_tag" true || manual_failure
  if [[ -d "$safety_parent" && ! -L "$safety_parent" ]]; then
    rm -f -- "$safety_parent/current-version"
    rmdir -- "$safety_parent" 2>/dev/null || true
  elif [[ -e "$safety_parent" ]]; then
    manual_failure
  fi
}

recover_deploy() {
  local previous_tag="${marker[previous_tag]:-}"
  local original_previous_tag="${marker[original_previous_tag]:-}"
  local backup_dir="${marker[backup_dir]:-}"
  validate_tag_or_none "$previous_tag" || {
    echo "invalid deploy previous tag; transaction marker retained" >&2
    exit 6
  }
  validate_tag_or_none "$original_previous_tag" || {
    echo "invalid deploy original previous tag; transaction marker retained" >&2
    exit 6
  }
  validate_backup_dir "$backup_dir" || {
    echo "invalid deploy backup path; transaction marker retained" >&2
    exit 6
  }

  if [[ "$previous_tag" == none ]]; then
    IMAGE_TAG="${marker[target_tag]}"
  else
    IMAGE_TAG="$previous_tag"
  fi
  export IMAGE_TAG
  compose stop backend frontend || manual_failure
  cleanup_partial_backup "$backup_dir" || manual_failure
  if [[ "$previous_tag" == none ]]; then
    rm -f -- "$CURRENT_FILE"
  else
    compose up -d --pull never backend || manual_failure
    compose up -d --pull never frontend || manual_failure
    wait_http "http://127.0.0.1:3000/" || manual_failure
    wait_http "${PUBLIC_BASE_URL%/}/" || manual_failure
    verify_runtime_version "$previous_tag" || manual_failure
    atomic_write "$previous_tag" "$CURRENT_FILE" || manual_failure
  fi

  if [[ "$original_previous_tag" == none ]]; then
    rm -f -- "$PREVIOUS_FILE"
  else
    atomic_write "$original_previous_tag" "$PREVIOUS_FILE" || manual_failure
  fi
}

case "${marker[operation]}" in
  restore) recover_restore ;;
  deploy) recover_deploy ;;
esac

rm -f -- "$TRANSACTION_FILE"
echo "interrupted ${marker[operation]} transaction recovered"
