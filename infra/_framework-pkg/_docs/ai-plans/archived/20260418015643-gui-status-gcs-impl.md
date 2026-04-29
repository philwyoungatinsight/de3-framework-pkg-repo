# Implementation Plan: GCS-native Unit & Wave Status

Design spec: `docs/ai-plans/gui-status-gcs.md`

---

## Overview

Write unit and wave status directly to GCS as append-only timestamped objects.
Remove the GUI's `.terragrunt-cache` Tier 1 poll loop.
On GUI startup, sync both `unit_status/` and `wave_status/` from GCS as concurrent
background jobs to recover state from before this session.
MaaS live progress remains local-only (no GCS prefix).

---

## Files to create

| Path | Purpose |
|------|---------|
| `utilities/bash/gcs-status.sh` | Shared bash helper: `gcs_write_unit_status` |
| `utilities/python/gcs_status.py` | Python equivalent for the wave runner |
| `scripts/human-only-scripts/purge-gcs-status/run` | Purge old timestamped status objects, keep last N per unit/wave |

## Files to modify

| Path | Change |
|------|--------|
| `utilities/tg-scripts/write-exit-status/run` | Source `gcs-status.sh`; call `gcs_write_unit_status` fire-and-forget at end |
| `run` (wave runner, Python) | Import `gcs_status.py`; call `write_wave_status` at phase start/end in `run_tg()` and `run_ansible_playbook()` |
| `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` | Remove Tier 1 loop body; add `unit_status/` + `wave_status/` GCS sync on `on_load`; merge GCS wave history into waves panel |
| `infra/gcp-pkg/_setup/seed` | Add GCS lifecycle rules (180-day expiry) on `unit_status/` and `wave_status/` prefixes after bucket creation |

---

## Step 1 — `utilities/bash/gcs-status.sh`

New file. Sourced by any bash script that needs to write status.

```bash
#!/usr/bin/env bash
# Shared helper for writing unit status to GCS.
# Source this file after set_env.sh (requires _GCS_STATE_BUCKET or reads framework.yaml).

_gcs_status_bucket() {
  # Return bucket name. Prefer env var set by set_env.sh; fall back to framework.yaml.
  if [[ -n "${_GCS_STATE_BUCKET:-}" ]]; then
    echo "$_GCS_STATE_BUCKET"
    return
  fi
  python3 -c "
import yaml, sys
with open('$(git rev-parse --show-toplevel)/config/framework.yaml') as f:
    d = yaml.safe_load(f)
print(d['framework']['backend']['config']['bucket'])
"
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
  bucket=$(_gcs_status_bucket)
  ts=$(_gcs_ts)
  uri="gs://${bucket}/unit_status/${unit_path}/${ts}.json"
  payload=$(printf '{"unit_path":"%s","status":"%s","last_apply_exit_code":%s,"finished_at":"%s","details":"%s","writer":"write-exit-status"}' \
    "$unit_path" "$status" "$exit_code" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$details")
  echo "$payload" | gsutil cp - "$uri" &>/dev/null &
}
```

**Design notes:**
- All GCS calls are fire-and-forget (`... &`). They must not block terraform or MaaS scripts.
- The bucket name is read from `_GCS_STATE_BUCKET` env var if set by `set_env.sh`, otherwise
  parsed from `config/framework.yaml`. Verify which env var `set_env.sh` actually exports for
  the bucket — search for `GCS` or `BUCKET` in `set_env.sh` before choosing the var name.
- `gsutil` auth is inherited from `GOOGLE_APPLICATION_CREDENTIALS` already set by `root.hcl`.

---

## Step 2 — `utilities/tg-scripts/write-exit-status/run`

After the existing `mv -f "$TMP" "${STATUS_DIR}/exit-${REL_FULL}.yaml"` line, add:

```bash
# Source GCS status helper and write unit status (fire-and-forget).
source "$(git rev-parse --show-toplevel)/utilities/bash/gcs-status.sh"
EXIT_CODE=0
[[ "$STATUS" == "fail" ]] && EXIT_CODE=1
gcs_write_unit_status "$UNIT_PATH" "$STATUS" "$EXIT_CODE"
```

The local YAML write at line 44 is kept as-is (Tier 0 local cache path unchanged).

---

## Step 3 — `utilities/python/gcs_status.py`

New Python module for the wave runner.

```python
"""GCS status helpers for the wave runner."""
from __future__ import annotations
import json, subprocess, threading
from datetime import datetime, timezone
from pathlib import Path


def _bucket() -> str:
    import yaml
    root = Path(__file__).resolve().parents[2]
    with open(root / "config/framework.yaml") as f:
        d = yaml.safe_load(f)
    return d["framework"]["backend"]["config"]["bucket"]


def _ts() -> str:
    """ISO-8601 UTC timestamp safe for GCS keys (colons → hyphens)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _gcs_put_async(uri: str, payload: dict) -> None:
    """Write JSON to a GCS URI in a background thread (fire-and-forget)."""
    data = json.dumps(payload).encode()
    def _run():
        proc = subprocess.Popen(
            ["gsutil", "cp", "-", uri],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.communicate(data)
    threading.Thread(target=_run, daemon=True).start()


def write_wave_status(
    wave_name: str,
    phase: str,
    status: str,
    *,
    started_at: str | None = None,
    units_total: int = 0,
    units_ok: int = 0,
    units_fail: int = 0,
) -> None:
    """
    Write wave_status/<wave_name>/<ts>.json.
    Call with status='running' at phase start, status='ok'|'fail' at phase end.
    """
    bucket = _bucket()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload: dict = {
        "wave_name": wave_name,
        "phase": phase,
        "status": status,
        "updated_at": now,
        "units_total": units_total,
        "units_ok": units_ok,
        "units_fail": units_fail,
    }
    if started_at:
        payload["started_at"] = started_at
    if status in ("ok", "fail"):
        payload["finished_at"] = now
    uri = f"gs://{bucket}/wave_status/{wave_name}/{_ts()}.json"
    _gcs_put_async(uri, payload)
```

---

## Step 4 — `run` (wave runner)

**Read** the file fully before editing. Key functions and lines:
- `run_tg()`: lines 373–382 — logs phase start/done markers
- `run_ansible_playbook()`: lines 385–399 — logs precheck/test-playbook markers

**Import** at top of `run` (after existing imports):

```python
sys.path.insert(0, str(Path(__file__).parent / "utilities/python"))
import gcs_status
```

**In `run_tg()`**, add `gcs_status.write_wave_status(...)` calls:
- Before the terragrunt subprocess starts: `status="running"`
- After it completes (success path): `status="ok"`
- In failure/exception path: `status="fail"`

Use the wave name already available in the function's scope. Read the function to find
the exact variable names for wave name, phase, and unit counts.

**In `run_ansible_playbook()`**, same pattern for precheck and test-playbook phases.

**Do not** change any existing log output — the `--- [wave] done ---` markers must remain
for backward compatibility until the GUI waves panel migration is complete.

---

## Step 5 — `homelab_gui.py`

**Read the full `local_state_watcher` function (line 8900 onward) before editing.**

### 5a — Remove Tier 1 (`.terragrunt-cache` scan)

Tier 1 starts at line ~9126 (`Find recently-changed local terraform.tfstate files`).
Remove the entire Tier 1 block. Leave Tier 0 (exit-*.yaml), Tier 0b (maas-*.yaml),
and Tier 3 (GUI exit-code files) intact.

### 5b — Add GCS sync helpers

Add two new async methods:

```python
async def _sync_unit_status_from_gcs(self):
    """
    Incremental sync: list unit_status/ objects newer than last sync,
    pull only changed ones, merge into local cache and Reflex state.
    Use self.unit_status_sync_after (str ISO timestamp) to filter gsutil ls output.
    On first call (empty string) pull everything.
    Parse each JSON object → call _write_unit_state + update unit_build_statuses.
    After sync, set self.unit_status_sync_after = now.
    """

async def _sync_wave_status_from_gcs(self):
    """
    On-load recovery: list wave_status/ objects, take the last per wave name,
    merge into wave_statuses Reflex state for waves not present in current run.log.
    run.log takes precedence for any wave it contains.
    Use self.wave_status_sync_after (str ISO timestamp) to skip already-seen objects.
    """
```

Add to Reflex state vars:
- `unit_status_sync_after: str = ""`
- `wave_status_sync_after: str = ""`

### 5c — Call both syncs from `on_load`

In `on_load()` after the existing `_read_unit_state()` call at line 5572, trigger
both sync methods as concurrent background tasks (non-blocking):

```python
yield HomeState._sync_unit_status_from_gcs
yield HomeState._sync_wave_status_from_gcs
```

### 5d — Merge GCS wave history into waves panel

In `refresh_wave_log_statuses()` (line 8362), after parsing `run.log`, merge in any
wave entries from the GCS sync that are not already present (i.e. waves from before
this session). `run.log` data takes precedence — do not overwrite a wave that appears
in the current log with a GCS-derived value.

### 5e — Remove MaaS field writes from unit status

The `maas_*` fields in `unit-state.yaml` are deprecated. Leave them in the schema for
backward compat but stop writing new values from the watcher. Tier 0b (maas-*.yaml)
continues unchanged — local display only, no GCS involvement.

---

## Step 6 — `scripts/human-only-scripts/purge-gcs-status/run`

New script. Standard structure: sources `set_env.sh`, reads bucket from framework.yaml.

**Algorithm:**

```python
#!/usr/bin/env python3
"""
Purge old timestamped GCS status objects, keeping the last KEEP_LAST per group.
Groups:
  unit_status/<unit_path>/  — keep last KEEP_LAST .json objects by name (lexicographic)
  wave_status/<wave_name>/  — keep last KEEP_LAST .json objects by name

Usage:
  KEEP_LAST=5 DRY_RUN=1 ./run      # preview
  KEEP_LAST=5 ./run                 # execute
"""
import os, subprocess, sys
from collections import defaultdict
from pathlib import Path

KEEP_LAST = int(os.environ.get("_GCS_STATUS_KEEP_LAST", "5"))
DRY_RUN   = os.environ.get("DRY_RUN", "0") == "1"

PREFIXES = ["unit_status/", "wave_status/"]
```

For each prefix:
1. `gsutil ls -l gs://<bucket>/<prefix>**` → parse URIs
2. Group by everything up to and including the second-to-last `/` (the unit_path or wave_name)
3. Sort each group ascending by URI (ISO timestamps → lexicographic = chronological)
4. `to_delete = group[:-KEEP_LAST]` (never deletes if len ≤ KEEP_LAST)
5. Batch delete: `gsutil -m rm <uri1> <uri2> ...`
6. Print summary per group; print total deleted count and bytes at end

Exit non-zero if any gsutil call fails.

---

## Step 7 — `infra/gcp-pkg/_setup/seed`

Read the seed script around the bucket creation (lines 1314–1379).

After bucket creation, add lifecycle rules using the GCS JSON API or `gsutil lifecycle set`:

```bash
# Add 180-day expiry on status prefixes as a backstop against purge not running.
cat > /tmp/gcs-lifecycle.json <<'EOF'
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {
        "age": 180,
        "matchesPrefix": ["unit_status/", "wave_status/"]
      }
    }
  ]
}
EOF
gsutil lifecycle set /tmp/gcs-lifecycle.json "gs://${BUCKET_NAME}"
rm /tmp/gcs-lifecycle.json
```

`matchesPrefix` requires the GCS lifecycle JSON format (not the XML format).
Verify the seed script uses `gsutil` or gcloud API calls for bucket config and match the style.

---

## Local file cleanup

### What is removed

| Artifact | Where | Reason |
|----------|-------|--------|
| Tier 1 loop body | `homelab_gui.py` ~line 9126 | Replaced by GCS incremental sync; `.terragrunt-cache` scan is the whole problem |
| `gcs_state_mtimes` Reflex state var | `homelab_gui.py` | Replaced by `unit_status_sync_after` + `wave_status_sync_after` |
| MaaS field writes to `unit-state.yaml` | `homelab_gui.py` watcher | No longer written; fields left in schema for backward compat but always empty going forward |
| "Validate (GCS)" full `gsutil ls -l -r` scan | `homelab_gui.py` | Replaced by incremental `unit_status/` sync; validate button triggers a full re-sync instead |

### What is intentionally kept

| Artifact | Why it stays |
|----------|-------------|
| `$_DYNAMIC_DIR/unit-status/exit-*.yaml` | Still the fast local push path: `write-exit-status/run` notifies the GUI watcher within one poll cycle (8 s) without a GCS round-trip. GCS is the shared truth store; the local file is the inter-process signal. |
| `$_DYNAMIC_DIR/unit-status/maas-*.yaml` | Still written by MaaS lifecycle scripts and read by Tier 0b for local live display. No GCS equivalent. |
| `$_GUI_DIR/homelab_gui_apply_*.exit` (Tier 3) | Still written by `apply_unit()` for GUI-initiated applies. Root.hcl after-hooks also fire for GUI applies (since they go through terragrunt), so Tier 0 handles the GCS write — but Tier 3 remains as the in-process fast path for updating the GUI's Reflex state immediately after `apply_unit()` returns. |
| `~/.run-waves-logs/unit-state.yaml` | Transitions from primary store to local read-cache. Still written after every status update (unchanged) so the GUI loads instantly on restart without a GCS round-trip. |

### Future cleanup (out of scope)

Once the GUI exclusively reads unit status from GCS on-load:
- Tier 3 (`$_GUI_DIR/homelab_gui_apply_*.exit`) can be removed if `apply_unit()`
  instead polls the GCS `unit_status/` prefix for its own unit after apply completes.
- The local `exit-*.yaml` files become redundant if the watcher switches to watching
  the GCS `unit_status/` prefix directly (e.g. via a short-poll on the incremental sync).
  This is a larger refactor and is deferred.

---

## Open questions to resolve before coding

1. **Bucket env var name**: check `set_env.sh` for an existing `_GCS_STATE_BUCKET` or
   equivalent. If it exists, use it in `gcs-status.sh` instead of parsing `framework.yaml`.

2. **Wave name variable in `run_tg()` and `run_ansible_playbook()`**: read the functions to
   find the exact Python variable holding the wave name. The log markers use it; find it there.

3. **`gsutil lifecycle set` with `matchesPrefix`**: test that the GCS lifecycle JSON condition
   key `matchesPrefix` is supported in the project's gsutil version. If not, use separate rules
   or set via `gcloud storage buckets update`.

---

## Commit plan

1. `utilities/bash/gcs-status.sh` + `utilities/python/gcs_status.py` — helpers only, no behaviour change
2. `write-exit-status/run` — wire unit_status writes
3. `run` — wire wave_status writes
4. `scripts/human-only-scripts/purge-gcs-status/run` — purge script
5. `homelab_gui.py` — remove Tier 1, add unit_status + wave_status GCS sync on load, merge wave history
6. `infra/gcp-pkg/_setup/seed` — lifecycle rules

Each commit is independently deployable. Steps 1–4 add GCS writes without changing any
read path; step 5 is the only change visible to users.
