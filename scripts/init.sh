#!/usr/bin/env bash
# Create .env from .env.example and fill every empty secret with a random value.
# Safe to re-run: existing values are never touched.
set -euo pipefail
cd "$(dirname "$0")/.."
env_file=${ENV_FILE:-.env}

[ -f "$env_file" ] || { cp .env.example "$env_file"; echo "created $env_file"; }

fill() { # fill VAR <random bytes> [prefix]
  grep -q "^$1=$" "$env_file" || return 0
  local value
  value="${3:-}$(openssl rand -hex "$2")"
  sed -i.bak "s|^$1=$|$1=$value|" "$env_file" && rm "$env_file.bak"
  echo "generated $1"
}
fill LITELLM_MASTER_KEY 24 sk-
fill WEBUI_SECRET_KEY 32
fill CREDS_KEY 32          # LibreChat: 32 bytes
fill CREDS_IV 16           # LibreChat: 16 bytes
fill JWT_SECRET 32
fill JWT_REFRESH_SECRET 32
fill MEILI_MASTER_KEY 16

cat <<EOF

Next:
  1. Put your OPENROUTER_API_KEY in $env_file
  2. docker compose --profile openwebui --profile librechat up -d
  3. ./scripts/smoke-test.sh
EOF
