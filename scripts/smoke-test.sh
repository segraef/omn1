#!/usr/bin/env bash
# Call every model the gateway serves once and report pass/fail per model.
# Needs: curl, jq, a running gateway (docker compose up -d).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
env_file=${ENV_FILE:-.env}
gw=${GATEWAY_URL:-http://localhost:4000}
auth="Authorization: Bearer $(sed -n 's/^LITELLM_MASTER_KEY=//p' "$env_file")"
failed=0

call() { # call <model> <chat|image_generation>
  local model=$1 mode=$2 body path out code secs
  if [ "$mode" = image_generation ]; then
    path=images/generations
    body=$(jq -nc --arg m "$model" '{model:$m, prompt:"a small red circle on a white background", size:"1024x1024", quality:"low"}')
  else
    path=chat/completions
    body=$(jq -nc --arg m "$model" '{model:$m, messages:[{role:"user", content:"Reply with the single word: ok"}]}')
  fi
  out=$(mktemp)
  read -r code secs < <(curl -s -m 180 -o "$out" -w '%{http_code} %{time_total}\n' \
    "$gw/v1/$path" -H "$auth" -H 'Content-Type: application/json' -d "$body")
  if [ "${code:-000}" = 200 ] && jq -e '.choices[0].message or .data[0].b64_json or .data[0].url' "$out" >/dev/null 2>&1; then
    printf '  PASS  %-16s %6.1fs\n' "$model" "$secs"
  else
    printf '  FAIL  %-16s HTTP %s  %s\n' "$model" "${code:-000}" "$(jq -r '.error.message // empty' "$out" 2>/dev/null | head -c 160)"
    failed=1
  fi
  rm -f "$out"
}

info=$(curl -sf "$gw/v1/model/info" -H "$auth") || { echo "gateway not reachable at $gw"; exit 1; }
while IFS=$'\t' read -r m mode; do call "$m" "$mode"; done < <(
  jq -r '.data[] | [.model_name, (.model_info.mode // "chat")] | @tsv' <<<"$info")

if [ $failed = 0 ]; then echo "all passed"; else echo "some checks failed"; exit 1; fi
