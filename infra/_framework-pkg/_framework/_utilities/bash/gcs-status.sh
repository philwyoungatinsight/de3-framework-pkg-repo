#!/usr/bin/env bash
# Shared helper for writing unit/wave status to GCS.
# Source this file after set_env.sh (_GCS_BUCKET must be exported).

_gcs_status_bucket() {
  if [[ -z "${_GCS_BUCKET:-}" ]]; then
    echo "ERROR: _GCS_BUCKET is not set — source set_env.sh before running" >&2
    return 1
  fi
  echo "$_GCS_BUCKET"
}

_gcs_ts() {
  # ISO-8601 UTC timestamp safe for GCS object keys (colons → hyphens).
  date -u +"%Y-%m-%dT%H-%M-%SZ"
}

# gcs_write_unit_status <unit_path> <status> <exit_code> [details]
# Writes unit_status/<unit_path>/<ts>.json fire-and-forget.
gcs_write_unit_status() {
  local unit_path="$1" status="$2" exit_code="$3" details="${4:-}"
  local bucket ts uri payload
  bucket=$(_gcs_status_bucket) || return 0
  ts=$(_gcs_ts)
  uri="gs://${bucket}/unit_status/${unit_path}/${ts}.json"
  payload=$(printf '{"unit_path":"%s","status":"%s","last_apply_exit_code":%s,"finished_at":"%s","details":"%s","writer":"write-exit-status"}' \
    "$unit_path" "$status" "$exit_code" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$details")
  echo "$payload" | gsutil cp - "$uri" &>/dev/null &
}
