#!/usr/bin/env bash

wait_http() {
  local url="$1"
  local attempts="${2:-$HTTP_ATTEMPTS}"
  local delay_seconds="${3:-$HTTP_DELAY_SECONDS}"
  local attempt response status
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
      if [[ "$status" == 200 ]]; then
        return 0
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
        printf '%s' "$body" | command python3 -I -c '
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

  verify_service_image backend "$expected_sha" || return 1
  verify_service_image frontend "$expected_sha" || return 1
  wait_version_json "http://127.0.0.1:8000/health" "$expected_sha" true || return 1
  wait_version_json "http://127.0.0.1:3000/version.json" "$expected_sha" || return 1
  wait_version_json "${PUBLIC_BASE_URL%/}/health" "$expected_sha" true || return 1
  wait_version_json "${PUBLIC_BASE_URL%/}/version.json" "$expected_sha"
}
