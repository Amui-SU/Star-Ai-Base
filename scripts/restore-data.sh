#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if (( $# != 1 )); then
  echo "usage: $0 <backup.tar.gz>" >&2
  exit 2
fi

readonly DEPLOY_ROOT="${ZHIKU_DEPLOY_ROOT:-/opt/zhiku-cloud}"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly PRODUCTION_PREFLIGHT="$SCRIPT_DIR/production-preflight.sh"
readonly RUNTIME_ATTESTATION="$SCRIPT_DIR/runtime-attestation.sh"
readonly ARCHIVE_INSPECTOR="$SCRIPT_DIR/inspect-restore-archive.py"
readonly COMPOSE_FILE="$DEPLOY_ROOT/compose.production.yml"
readonly DEPLOY_DIR="$DEPLOY_ROOT/deploy"
readonly DEPLOY_ENV="$DEPLOY_DIR/.env.deploy"
readonly APP_ENV="$DEPLOY_DIR/.env.production"
readonly CURRENT_FILE="$DEPLOY_DIR/current-version"
readonly TRANSACTION_FILE="$DEPLOY_DIR/transaction"
readonly DATA_DIR="$DEPLOY_ROOT/data"
readonly BACKUPS_DIR="$DEPLOY_ROOT/backups"
readonly HTTP_ATTEMPTS="${ZHIKU_RESTORE_HTTP_ATTEMPTS:-30}"
readonly HTTP_DELAY_SECONDS="${ZHIKU_RESTORE_HTTP_DELAY_SECONDS:-2}"
readonly MAX_ARCHIVE_MEMBERS="${ZHIKU_RESTORE_MAX_MEMBERS:-100000}"
readonly MAX_ARCHIVE_BYTES="${ZHIKU_RESTORE_MAX_BYTES:-21474836480}"
readonly DISK_RESERVE_BYTES="${ZHIKU_RESTORE_DISK_RESERVE_BYTES:-2147483648}"
readonly BACKUP_INPUT="$1"

if [[ ! "$HTTP_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] ||
  [[ ! "$HTTP_DELAY_SECONDS" =~ ^[0-9]+$ ]] ||
  [[ ! "$MAX_ARCHIVE_MEMBERS" =~ ^[1-9][0-9]*$ ]] ||
  [[ ! "$MAX_ARCHIVE_BYTES" =~ ^[1-9][0-9]*$ ]] ||
  [[ ! "$DISK_RESERVE_BYTES" =~ ^[0-9]+$ ]]; then
  echo "invalid restore retry or archive limit configuration" >&2
  exit 2
fi

for command_name in docker curl flock mktemp realpath cp mv chown chmod find grep tr sleep df awk rm rmdir python3; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "missing required command: $command_name" >&2
    exit 3
  }
done
[[ -f "$ARCHIVE_INSPECTOR" ]] || {
  echo "missing archive inspector: $ARCHIVE_INSPECTOR" >&2
  exit 3
}

for required_file in "$PRODUCTION_PREFLIGHT" "$RUNTIME_ATTESTATION" "$COMPOSE_FILE" "$DEPLOY_ENV" "$APP_ENV" "$CURRENT_FILE"; do
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

exec 9>"$DEPLOY_DIR/deploy.lock"
if ! flock -n 9; then
  echo "another deployment or restore is already in progress" >&2
  exit 7
fi
if [[ -e "$TRANSACTION_FILE" ]]; then
  echo "an interrupted transaction exists; run $DEPLOY_ROOT/scripts/recover-interrupted.sh" >&2
  exit 7
fi

# shellcheck source=production-preflight.sh
source "$PRODUCTION_PREFLIGHT"
production_preflight "$DEPLOY_ENV" "$APP_ENV"
readonly ACR_REGISTRY ACR_NAMESPACE PUBLIC_BASE_URL

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

CURRENT_TAG="$(tr -d '[:space:]' < "$CURRENT_FILE")"
[[ "$CURRENT_TAG" =~ ^[0-9a-f]{40}$ ]] || {
  echo "deploy/current-version must contain one lowercase 40-character SHA" >&2
  exit 6
}
readonly CURRENT_TAG
IMAGE_TAG="$CURRENT_TAG"
export IMAGE_TAG

if ! UNCOMPRESSED_BYTES="$(
  command python3 -I "$ARCHIVE_INSPECTOR" \
    "$BACKUP_REAL" "$MAX_ARCHIVE_MEMBERS" "$MAX_ARCHIVE_BYTES"
)"; then
  echo "backup inspection failed" >&2
  exit 8
fi
[[ "$UNCOMPRESSED_BYTES" =~ ^[0-9]+$ ]] || {
  echo "archive inspector returned an invalid size" >&2
  exit 8
}
if ! AVAILABLE_KIB="$(df -Pk -- "$DEPLOY_ROOT" | awk 'NR > 1 { available = $4 } END { print available }')"; then
  echo "failed to measure restore filesystem free space" >&2
  exit 7
fi
[[ "$AVAILABLE_KIB" =~ ^[0-9]+$ ]] || {
  echo "invalid free space reported by df" >&2
  exit 7
}
ARCHIVE_KIB=$(( (UNCOMPRESSED_BYTES + 1023) / 1024 ))
RESERVE_KIB=$(( (DISK_RESERVE_BYTES + 1023) / 1024 ))
REQUIRED_KIB=$(( ARCHIVE_KIB + RESERVE_KIB ))
if (( AVAILABLE_KIB < REQUIRED_KIB )); then
  echo "insufficient free space for restore: need ${REQUIRED_KIB} KiB, have ${AVAILABLE_KIB} KiB" >&2
  exit 7
fi
readonly UNCOMPRESSED_BYTES AVAILABLE_KIB ARCHIVE_KIB RESERVE_KIB REQUIRED_KIB

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

STAGED_DATA=""
SAFETY_PARENT=""
RESTORE_SUCCEEDED=false
MUTATION_STARTED=false

safe_remove_staging() {
  local path="$1"
  case "$path" in
    "$DEPLOY_ROOT"/data.restore.*)
      [[ ! -L "$path" ]] || return 1
      rm -rf -- "$path"
      ;;
    *)
      echo "refusing to remove unexpected staging path: $path" >&2
      return 1
      ;;
  esac
}

safe_remove_pre_mutation_safety() {
  local path="$1"
  case "$path" in
    "$DEPLOY_ROOT"/data.safety.*)
      [[ ! -L "$path" && ! -e "$path/data" && ! -e "$path/failed-restored-data" ]] || return 1
      rm -f -- "$path/current-version"
      rmdir -- "$path"
      ;;
    *)
      echo "refusing to remove unexpected safety path: $path" >&2
      return 1
      ;;
  esac
}

report_retained_directories() {
  local original_exit_code="$?"
  if [[ -n "$STAGED_DATA" && -d "$STAGED_DATA" ]]; then
    if [[ "$MUTATION_STARTED" == false ]]; then
      safe_remove_staging "$STAGED_DATA" ||
        echo "failed to clean restore staging directory: $STAGED_DATA" >&2
    else
      echo "retained restore staging directory for inspection: $STAGED_DATA" >&2
    fi
  fi
  if [[ "$RESTORE_SUCCEEDED" == false && -n "$SAFETY_PARENT" && -d "$SAFETY_PARENT" ]]; then
    if [[ "$MUTATION_STARTED" == false ]]; then
      safe_remove_pre_mutation_safety "$SAFETY_PARENT" ||
        echo "retained restore safety directory for inspection: $SAFETY_PARENT" >&2
    else
      echo "retained restore safety directory for inspection: $SAFETY_PARENT" >&2
    fi
  fi
  return "$original_exit_code"
}

trap report_retained_directories EXIT

if ! STAGED_DATA="$(mktemp -d "$DEPLOY_ROOT/data.restore.XXXXXX")"; then
  echo "failed to create restore staging directory" >&2
  exit 7
fi
readonly STAGED_DATA
chmod 0700 "$STAGED_DATA"

if ! command python3 -I - "$BACKUP_REAL" "$STAGED_DATA" "$MAX_ARCHIVE_MEMBERS" "$MAX_ARCHIVE_BYTES" <<'PY'
import pathlib
import shutil
import sqlite3
import sys
import tarfile

archive_path, destination_path, max_members_text, max_bytes_text = sys.argv[1:]
destination = pathlib.Path(destination_path).resolve()
max_members = int(max_members_text)
max_bytes = int(max_bytes_text)
seen = set()


def validate_sqlite(database, required_tables=(), require_schema=False):
    if not database.is_file() or database.stat().st_size == 0:
        raise ValueError(f"SQLite validation failed: missing or empty {database.name}")
    connection = None
    try:
        connection = sqlite3.connect(
            f"{database.resolve().as_uri()}?mode=ro", uri=True
        )
        integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
        if integrity != ["ok"]:
            raise ValueError(
                f"SQLite validation failed for {database.name}: {integrity!r}"
            )
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        missing = set(required_tables) - tables
        if missing:
            raise ValueError(
                f"SQLite validation failed for {database.name}: missing tables {sorted(missing)!r}"
            )
        if require_schema and not tables:
            raise ValueError(
                f"SQLite validation failed for {database.name}: empty schema"
            )
    except sqlite3.DatabaseError as error:
        raise ValueError(
            f"SQLite validation failed for {database.name}: {error}"
        ) from error
    finally:
        if connection is not None:
            connection.close()

try:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if not members:
            raise ValueError("empty archive")
        total_bytes = sum(member.size for member in members if member.isfile())
        if len(members) > max_members or total_bytes > max_bytes:
            raise ValueError(
                "archive resource limit exceeded: "
                f"members={len(members)}/{max_members}, bytes={total_bytes}/{max_bytes}"
            )
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
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"unreadable member: {raw_name!r}")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)

    validate_sqlite(
        destination / "bilibili_rag.db",
        required_tables=("system_users", "knowledge_bases"),
    )
    validate_sqlite(
        destination / "chroma_db" / "chroma.sqlite3",
        require_schema=True,
    )
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

DATA_SWAP_BEGUN=false

atomic_write() {
  local value="$1"
  local destination="$2"
  local temporary

  temporary="$(mktemp "${destination}.tmp.XXXXXX")" || return 1
  if ! printf '%s\n' "$value" > "$temporary"; then
    rm -f -- "$temporary"
    return 1
  fi
  if ! mv -- "$temporary" "$destination"; then
    rm -f -- "$temporary"
    return 1
  fi
}

write_restore_marker() {
  local phase="$1"
  atomic_write "version=1
operation=restore
phase=$phase
current_tag=$CURRENT_TAG
staged_data=$STAGED_DATA
safety_parent=$SAFETY_PARENT" "$TRANSACTION_FILE"
}

disable_failure_traps() {
  trap - ERR HUP INT TERM
}

recover_data_and_backend() {
  local data_is_safe=false

  if ! compose stop backend; then
    echo "automatic recovery could not stop backend; backend state is unknown" >&2
    print_manual_recovery_instructions
    return 1
  fi

  if [[ "$DATA_SWAP_BEGUN" == false ]]; then
    data_is_safe=true
  elif [[ -d "$SAFETY_PARENT/data" ]]; then
    if [[ -e "$DATA_DIR" ]]; then
      if ! mv "$DATA_DIR" "$SAFETY_PARENT/failed-restored-data"; then
        print_manual_recovery_instructions
        return 1
      fi
    fi
    if ! mv "$SAFETY_PARENT/data" "$DATA_DIR"; then
      print_manual_recovery_instructions
      return 1
    fi
    data_is_safe=true
  elif [[ -d "$DATA_DIR" && -d "$STAGED_DATA" ]]; then
    # The first same-filesystem rename did not complete; original data remains.
    data_is_safe=true
  else
    print_manual_recovery_instructions
    return 1
  fi

  if [[ "$data_is_safe" != true ]]; then
    print_manual_recovery_instructions
    return 1
  fi
  write_restore_marker rollback_ready || return 1
  IMAGE_TAG="$CURRENT_TAG"
  export IMAGE_TAG
  compose up -d --pull never backend || return 1
  wait_version_json "http://127.0.0.1:8000/health/version" "$CURRENT_TAG" true || return 1
  wait_version_json "${PUBLIC_BASE_URL%/}/health/version" "$CURRENT_TAG" true
}

print_manual_recovery_instructions() {
  echo "automatic data recovery failed; backend left stopped" >&2
  echo "old data: $SAFETY_PARENT/data" >&2
  echo "failed restored data: $SAFETY_PARENT/failed-restored-data" >&2
  echo "active data path: $DATA_DIR" >&2
  echo "inspect these paths, restore the old data to the active path, then start the exact current SHA manually" >&2
}

on_error() {
  local original_exit_code="$?"
  disable_failure_traps
  if [[ "$MUTATION_STARTED" == true ]]; then
    if recover_data_and_backend; then
      rm -f -- "$TRANSACTION_FILE"
    else
      echo "automatic restore recovery failed; run $DEPLOY_ROOT/scripts/recover-interrupted.sh" >&2
    fi
  fi
  exit "$original_exit_code"
}

on_signal() {
  local signal_exit_code="$1"
  disable_failure_traps
  if [[ "$MUTATION_STARTED" == true ]]; then
    if recover_data_and_backend; then
      rm -f -- "$TRANSACTION_FILE"
    else
      echo "automatic restore recovery failed after signal; run $DEPLOY_ROOT/scripts/recover-interrupted.sh" >&2
    fi
  fi
  exit "$signal_exit_code"
}

trap on_error ERR
trap 'on_signal 129' HUP
trap 'on_signal 130' INT
trap 'on_signal 143' TERM

write_restore_marker prepared
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

DATA_SWAP_BEGUN=true
mv "$DATA_DIR" "$SAFETY_PARENT/data"
write_restore_marker old_moved
mv "$STAGED_DATA" "$DATA_DIR"
write_restore_marker new_active

IMAGE_TAG="$CURRENT_TAG"
export IMAGE_TAG
compose up -d --pull never backend
wait_version_json "http://127.0.0.1:8000/health/version" "$CURRENT_TAG" true
wait_version_json "${PUBLIC_BASE_URL%/}/health/version" "$CURRENT_TAG" true

MUTATION_STARTED=false
RESTORE_SUCCEEDED=true
rm -f -- "$TRANSACTION_FILE"
disable_failure_traps
echo "data restore succeeded from $BACKUP_REAL; safety copy: $SAFETY_PARENT/data"
