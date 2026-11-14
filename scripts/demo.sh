#!/usr/bin/env bash
# Upload one sample PDF per parser, poll the batches until done and print summaries.
# Usage: scripts/demo.sh [base_url]   (default http://localhost:8000)
# Set DEMO_WATCH_SSE=1 to stream each batch from /batches/{id}/events instead of polling.
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
SAMPLES="$(cd "$(dirname "$0")/../samples" && pwd)"
TIMEOUT="${DEMO_TIMEOUT_SECONDS:-180}"

command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }
curl -fsS "$BASE_URL/health" >/dev/null || { echo "API not reachable at $BASE_URL" >&2; exit 1; }

upload() { # <pdf> <parser> -> batch id
  curl -fsS -F "files=@$1" -F "parser=$2" "$BASE_URL/documents" | jq -r .batch_id
}

PYPDF_BATCH="$(upload "$SAMPLES/sample-text.pdf" pypdf)"
LLM_BATCH="$(upload "$SAMPLES/sample-layout.pdf" llm)"

deadline=$((SECONDS + TIMEOUT))
for entry in "pypdf:$PYPDF_BATCH" "llm:$LLM_BATCH"; do
  parser="${entry%%:*}"
  batch_id="${entry#*:}"
  echo "== parser=$parser batch=$batch_id"
  if [ "${DEMO_WATCH_SSE:-0}" = "1" ]; then
    curl -fsSN --max-time "$TIMEOUT" "$BASE_URL/batches/$batch_id/events" | while IFS= read -r line; do
      case "$line" in event:*) echo "  $line" ;; esac
      [ "$line" = "event: done" ] && break
    done || true
  fi
  while :; do
    batch="$(curl -fsS "$BASE_URL/batches/$batch_id")"
    pending="$(jq '[.documents[] | select(.status != "completed" and .status != "failed")] | length' <<<"$batch")"
    [ "$pending" -eq 0 ] && break
    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "timed out waiting for batch $batch_id" >&2
      exit 1
    fi
    sleep 2
  done
  jq -r '.documents[] | "\(.filename): status=\(.status) summary_status=\(.summary_status) pages=\(.page_count // 0)\n  error: \(.error // "-")\n  summary: \(.summary // "-")"' <<<"$batch"
done
