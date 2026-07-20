#!/usr/bin/env bash

production_preflight_invalid_deploy() {
  echo "invalid deployment environment: $1" >&2
  exit 4
}

production_preflight_invalid_app() {
  echo "invalid production application environment: $1" >&2
  exit 6
}

production_preflight() {
  local deploy_env="$1"
  local app_env="$2"
  local line key value first_character last_character
  local seen_registry=false
  local seen_namespace=false
  local seen_public_url=false
  local smtp_any=false
  local smtp_complete=false
  local google_any=false
  local google_complete=false
  local -A seen_app_keys=()

  ACR_REGISTRY=""
  ACR_NAMESPACE=""
  PUBLIC_BASE_URL=""

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" == *=* ]] || production_preflight_invalid_deploy "expected KEY=VALUE"

    key="${line%%=*}"
    value="${line#*=}"
    case "$key" in
      ACR_REGISTRY)
        [[ "$seen_registry" == false ]] || production_preflight_invalid_deploy "duplicate ACR_REGISTRY"
        ACR_REGISTRY="$value"
        seen_registry=true
        ;;
      ACR_NAMESPACE)
        [[ "$seen_namespace" == false ]] || production_preflight_invalid_deploy "duplicate ACR_NAMESPACE"
        ACR_NAMESPACE="$value"
        seen_namespace=true
        ;;
      PUBLIC_BASE_URL)
        [[ "$seen_public_url" == false ]] || production_preflight_invalid_deploy "duplicate PUBLIC_BASE_URL"
        PUBLIC_BASE_URL="$value"
        seen_public_url=true
        ;;
      *)
        production_preflight_invalid_deploy "unknown key: $key"
        ;;
    esac
  done < "$deploy_env"

  [[ "$seen_registry" == true ]] ||
    production_preflight_invalid_deploy "ACR_REGISTRY must be a supported Beijing ACR public endpoint"
  if [[ "$ACR_REGISTRY" == "your-instance-registry.cn-beijing.cr.aliyuncs.com" ||
    "$ACR_REGISTRY" == "crpi-your-instance.cn-beijing.personal.cr.aliyuncs.com" ]]; then
    production_preflight_invalid_deploy "ACR_REGISTRY still contains an example placeholder"
  fi
  if [[ "$ACR_REGISTRY" == "registry.cn-beijing.aliyuncs.com" ||
    "$ACR_REGISTRY" =~ ^[a-z0-9][a-z0-9-]*-registry\.cn-beijing\.cr\.aliyuncs\.com$ ||
    ( "$ACR_REGISTRY" =~ ^crpi-[a-z0-9][a-z0-9-]*\.cn-beijing\.personal\.cr\.aliyuncs\.com$ &&
      ! "$ACR_REGISTRY" =~ ^crpi-.*-vpc\.cn-beijing\.personal\.cr\.aliyuncs\.com$ ) ]]; then
    :
  else
    production_preflight_invalid_deploy "ACR_REGISTRY must be a supported Beijing ACR public endpoint"
  fi
  [[ "$seen_namespace" == true && "$ACR_NAMESPACE" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]] ||
    production_preflight_invalid_deploy "ACR_NAMESPACE has an unsafe value"
  [[ "$seen_public_url" == true ]] || production_preflight_invalid_deploy "PUBLIC_BASE_URL is required"
  [[ "$PUBLIC_BASE_URL" =~ ^https://[A-Za-z0-9][A-Za-z0-9.-]*(:[0-9]+)?(/[^[:space:]?#]*)?$ ]] ||
    production_preflight_invalid_deploy "PUBLIC_BASE_URL must be a valid HTTPS URL without credentials, query, or fragment"

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

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" == *=* ]] || production_preflight_invalid_app "expected KEY=VALUE"

    key="${line%%=*}"
    value="${line#*=}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || production_preflight_invalid_app "invalid key: $key"
    first_character="${value:0:1}"
    last_character="${value: -1}"
    if [[ "$first_character" == \" || "$first_character" == "'" ||
      "$last_character" == \" || "$last_character" == "'" ]]; then
      production_preflight_invalid_app "quoted values are not allowed for $key; Compose raw env values must be exact"
    fi
    [[ "$value" != REPLACE_* ]] || production_preflight_invalid_app "placeholder remains for $key"

    case "$key" in
      DEBUG|SESSION_COOKIE_SECURE|ADMIN_EMAILS|APP_ENCRYPTION_KEY|SMTP_HOST|SMTP_USER|SMTP_PASSWORD|SMTP_FROM|GOOGLE_CLIENT_ID|GOOGLE_CLIENT_SECRET|GOOGLE_REDIRECT_URI)
        [[ -z "${seen_app_keys[$key]+x}" ]] || production_preflight_invalid_app "duplicate key: $key"
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
  done < "$app_env"

  [[ "$DEBUG_VALUE" == false ]] || production_preflight_invalid_app "DEBUG must be false"
  [[ "${SESSION_COOKIE_SECURE_VALUE,,}" == true ]] || production_preflight_invalid_app "SESSION_COOKIE_SECURE must be true"
  [[ -n "$ADMIN_EMAILS_VALUE" ]] || production_preflight_invalid_app "ADMIN_EMAILS is required"
  [[ "${ADMIN_EMAILS_VALUE,,}" != *"admin@example"* && "${ADMIN_EMAILS_VALUE,,}" != *"@example."* ]] ||
    production_preflight_invalid_app "ADMIN_EMAILS must not use an example administrator"
  [[ "$APP_ENCRYPTION_KEY_VALUE" =~ ^[A-Za-z0-9_-]{43}=$ ]] ||
    production_preflight_invalid_app "APP_ENCRYPTION_KEY must be a 44-character URL-safe base64 Fernet key"

  if [[ -n "$SMTP_HOST_VALUE" || -n "$SMTP_USER_VALUE" || -n "$SMTP_PASSWORD_VALUE" || -n "$SMTP_FROM_VALUE" ]]; then
    smtp_any=true
    if [[ -n "$SMTP_HOST_VALUE" && -n "$SMTP_USER_VALUE" && -n "$SMTP_PASSWORD_VALUE" && -n "$SMTP_FROM_VALUE" ]]; then
      smtp_complete=true
    else
      production_preflight_invalid_app "SMTP login is partial; configure HOST, USER, PASSWORD, and FROM"
    fi
  fi

  if [[ -n "$GOOGLE_CLIENT_ID_VALUE" || -n "$GOOGLE_CLIENT_SECRET_VALUE" ]]; then
    google_any=true
    if [[ -n "$GOOGLE_CLIENT_ID_VALUE" && -n "$GOOGLE_CLIENT_SECRET_VALUE" ]]; then
      [[ "$GOOGLE_REDIRECT_URI_VALUE" == "https://zhiku-cloud.cn/system-auth/google/callback" ]] ||
        production_preflight_invalid_app "GOOGLE_REDIRECT_URI must use the canonical HTTPS callback"
      google_complete=true
    else
      production_preflight_invalid_app "Google login is partial; configure both client ID and secret"
    fi
  fi

  [[ "$smtp_any" == false || "$smtp_complete" == true ]] || production_preflight_invalid_app "SMTP login is incomplete"
  [[ "$google_any" == false || "$google_complete" == true ]] || production_preflight_invalid_app "Google login is incomplete"
  [[ "$smtp_complete" == true || "$google_complete" == true ]] || production_preflight_invalid_app "at least one usable login method is required"

  export ACR_REGISTRY ACR_NAMESPACE
}
