#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if (( $# != 1 )); then
  echo "usage: $0 <backup.tar.gz>" >&2
  exit 2
fi

readonly DEPLOY_ROOT="${ZHIKU_DEPLOY_ROOT:-/opt/zhiku-cloud}"
readonly COMPOSE_FILE="$DEPLOY_ROOT/compose.production.yml"
readonly DEPLOY_DIR="$DEPLOY_ROOT/deploy"
readonly DEPLOY_ENV="$DEPLOY_DIR/.env.deploy"
readonly APP_ENV="$DEPLOY_DIR/.env.production"
readonly CURRENT_FILE="$DEPLOY_DIR/current-version"
readonly DATA_DIR="$DEPLOY_ROOT/data"
readonly BACKUPS_DIR="$DEPLOY_ROOT/backups"
readonly PYTHON_BIN="${ZHIKU_RESTORE_PYTHON:-python3}"
readonly HTTP_ATTEMPTS="${ZHIKU_RESTORE_HTTP_ATTEMPTS:-30}"
readonly HTTP_DELAY_SECONDS="${ZHIKU_RESTORE_HTTP_DELAY_SECONDS:-2}"
readonly BACKUP_INPUT="$1"

if [[ ! "$HTTP_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] || [[ ! "$HTTP_DELAY_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "invalid restore health retry configuration" >&2
  exit 2
fi

for command_name in docker curl flock mktemp realpath cp mv chown chmod find grep tr sleep "$PYTHON_BIN"; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "missing required command: $command_name" >&2
    exit 3
  }
done

for required_file in "$COMPOSE_FILE" "$DEPLOY_ENV" "$APP_ENV" "$CURRENT_FILE"; do
  [[ -f "$required_file" ]] || {
    echo "missing required restore file: $required_file" >&2
    exit 4
  }
done
for required_directory in "$DATA_DIR" "$BACKUPS_DIR"; do
  [[ -d "$required_directory" ]] || {
    echo "missing required restore directory: $required_directory" >&2
    exit 4
  }
done

[[ ! -L "$BACKUP_INPUT" ]] || {
  echo "backup path must not be a symlink" >&2
  exit 5
}
if ! BACKUPS_REAL="$(realpath -e -- "$BACKUPS_DIR")"; then
  echo "failed to resolve backups directory" >&2
  exit 5
fi
if ! BACKUP_REAL="$(realpath -e -- "$BACKUP_INPUT")"; then
  echo "backup does not exist" >&2
  exit 5
fi
case "$BACKUP_REAL" in
  "$BACKUPS_REAL"/*) ;;
  *)
    echo "backup must resolve inside $BACKUPS_DIR" >&2
    exit 5
    ;;
esac
[[ -f "$BACKUP_REAL" ]] || {
  echo "backup must be a regular file" >&2
  exit 5
}
readonly BACKUPS_REAL BACKUP_REAL

CURRENT_TAG="$(tr -d '[:space:]' < "$CURRENT_FILE")"
[[ "$CURRENT_TAG" =~ ^[0-9a-f]{40}$ ]] || {
  echo "deploy/current-version must contain one lowercase 40-character SHA" >&2
  exit 6
}
readonly CURRENT_TAG
IMAGE_TAG="$CURRENT_TAG"
export IMAGE_TAG

PUBLIC_BASE_URL=""
seen_public_url=false
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  [[ "$line" == *=* ]] || {
    echo "invalid deployment environment" >&2
    exit 6
  }
  key="${line%%=*}"
  value="${line#*=}"
  if [[ "$key" == PUBLIC_BASE_URL ]]; then
    [[ "$seen_public_url" == false ]] || {
      echo "duplicate PUBLIC_BASE_URL" >&2
      exit 6
    }
    PUBLIC_BASE_URL="$value"
    seen_public_url=true
  fi
done < "$DEPLOY_ENV"
[[ "$seen_public_url" == true && "$PUBLIC_BASE_URL" =~ ^https://[A-Za-z0-9][A-Za-z0-9.-]*(:[0-9]+)?(/[^[:space:]?#]*)?$ ]] || {
  echo "PUBLIC_BASE_URL must be a valid HTTPS URL" >&2
  exit 6
}
readonly PUBLIC_BASE_URL

exec 9>"$DEPLOY_DIR/deploy.lock"
if ! flock -n 9; then
  echo "another deployment or restore is already in progress" >&2
  exit 7
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
  local expected_body='{"status":"healthy"}'
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

  for ((attempt = 1; attempt <= HTTP_ATTEMPTS; attempt += 1)); do
    if response="$(curl "${curl_options[@]}" "$url")"; then
      status="${response##*$'\n'}"
      body="${response%$'\n'*}"
      compact_body="$(printf '%s' "$body" | tr -d '[:space:]')"
      if [[ "$status" == 200 && "$compact_body" == "$expected_body" ]]; then
        return 0
      fi
    fi
    if (( attempt < HTTP_ATTEMPTS )); then
      sleep "$HTTP_DELAY_SECONDS"
    fi
  done

  echo "health check failed: $url" >&2
  return 1
}

if ! STAGED_DATA="$(mktemp -d "$DEPLOY_ROOT/data.restore.XXXXXX")"; then
  echo "failed to create restore staging directory" >&2
  exit 7
fi
readonly STAGED_DATA
chmod 0700 "$STAGED_DATA"

if ! "$PYTHON_BIN" - "$BACKUP_REAL" "$STAGED_DATA" <<'PY'
import pathlib
import shutil
import sys
import tarfile

archive_path, destination_path = sys.argv[1:]
destination = pathlib.Path(destination_path).resolve()
seen = set()

try:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if not members:
            raise ValueError("empty archive")
        for member in members:
            raw_name = member.name
            path = pathlib.PurePosixPath(raw_name)
            parts = tuple(part for part in path.parts if part not in ("", "."))
            if (
                path.is_absolute()
                or ".." in parts
                or "\\" in raw_name
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError(f"unsafe member: {raw_name!r}")
            if not parts:
                if member.isdir():
                    continue
                raise ValueError("archive root must be a directory")
            normalized = "/".join(parts)
            if normalized in seen:
                raise ValueError(f"duplicate member: {normalized!r}")
            seen.add(normalized)
            target = destination.joinpath(*parts)
            if destination not in target.parents:
                raise ValueError(f"escaping member: {raw_name!r}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=False)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"unreadable member: {raw_name!r}")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
except (OSError, tarfile.TarError, ValueError) as error:
    print(f"unsafe archive: {error}", file=sys.stderr)
    raise SystemExit(1)
PY
then
  echo "backup inspection or extraction failed" >&2
  exit 8
fi

[[ -s "$STAGED_DATA/bilibili_rag.db" ]] || {
  echo "backup is missing a non-empty bilibili_rag.db" >&2
  exit 8
}
[[ -d "$STAGED_DATA/chroma_db" ]] || {
  echo "backup is missing chroma_db" >&2
  exit 8
}
[[ -n "$(find "$STAGED_DATA/chroma_db" -type f -print -quit)" ]] || {
  echo "backup chroma_db has no files" >&2
  exit 8
}

if ! SAFETY_PARENT="$(mktemp -d "$DEPLOY_ROOT/data.safety.XXXXXX")"; then
  echo "failed to create restore safety directory" >&2
  exit 7
fi
readonly SAFETY_PARENT
chmod 0700 "$SAFETY_PARENT"
cp -a "$CURRENT_FILE" "$SAFETY_PARENT/current-version"
chown -R --reference="$DATA_DIR" "$STAGED_DATA"
chmod --reference="$DATA_DIR" "$STAGED_DATA"

MUTATION_STARTED=false
DATA_PRESERVATION_ATTEMPTED=false

disable_failure_traps() {
  trap - ERR HUP INT TERM
}

recover_data_and_backend() {
  local recovery_failed=false

  if [[ "$DATA_PRESERVATION_ATTEMPTED" == true && -d "$SAFETY_PARENT/data" ]]; then
    if [[ -e "$DATA_DIR" ]]; then
      mv "$DATA_DIR" "$SAFETY_PARENT/failed-restored-data" || recovery_failed=true
    fi
    if [[ "$recovery_failed" == false ]]; then
      mv "$SAFETY_PARENT/data" "$DATA_DIR" || recovery_failed=true
    fi
  fi

  IMAGE_TAG="$CURRENT_TAG"
  export IMAGE_TAG
  compose up -d --pull never backend || recovery_failed=true
  if [[ "$recovery_failed" == false ]]; then
    wait_http "http://127.0.0.1:8000/health" || recovery_failed=true
    wait_http "${PUBLIC_BASE_URL%/}/health" || recovery_failed=true
  fi

  [[ "$recovery_failed" == false ]]
}

on_error() {
  local original_exit_code="$?"
  disable_failure_traps
  if [[ "$MUTATION_STARTED" == true ]]; then
    recover_data_and_backend || echo "automatic restore recovery failed; inspect the safety directory" >&2
  fi
  exit "$original_exit_code"
}

on_signal() {
  local signal_exit_code="$1"
  disable_failure_traps
  if [[ "$MUTATION_STARTED" == true ]]; then
    recover_data_and_backend || echo "automatic restore recovery failed after signal" >&2
  fi
  exit "$signal_exit_code"
}

trap on_error ERR
trap 'on_signal 129' HUP
trap 'on_signal 130' INT
trap 'on_signal 143' TERM

MUTATION_STARTED=true
compose stop backend
if ! backend_states="$(compose ps --all --format '{{.State}}' backend)"; then
  echo "failed to confirm that the backend stopped" >&2
  false
fi
if [[ -n "$backend_states" ]] && grep -Evqx '(exited|dead)' <<<"$backend_states"; then
  echo "backend did not stop; observed states: $backend_states" >&2
  false
fi

DATA_PRESERVATION_ATTEMPTED=true
mv "$DATA_DIR" "$SAFETY_PARENT/data"
mv "$STAGED_DATA" "$DATA_DIR"

IMAGE_TAG="$CURRENT_TAG"
export IMAGE_TAG
compose up -d --pull never backend
wait_http "http://127.0.0.1:8000/health"
wait_http "${PUBLIC_BASE_URL%/}/health"

MUTATION_STARTED=false
disable_failure_traps
echo "data restore succeeded from $BACKUP_REAL; safety copy: $SAFETY_PARENT/data"
