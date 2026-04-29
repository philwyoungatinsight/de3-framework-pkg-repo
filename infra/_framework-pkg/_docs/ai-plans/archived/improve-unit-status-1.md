# improve-unit-status-1: Accurate, Low-Latency Unit Status Without Excess GCS Calls

## Problem Statement

The current unit-status tracking system has four pain points:

1. **Stale final status.** Tier 1 (the local tfstate mtime watcher) calls `gsutil cat` after each
   detected change to get the resource count and determine ok/fail. This adds latency and burns GCS
   quota. More critically, `status: ok` is determined by resource count > 0, not by whether the apply
   actually succeeded — a timed-out MaaS commission returns `status: ok` because resources were
   written.

2. **Dead tracking during MaaS long-running phases.** Commission takes ~5 min, deploy ~10 min. During
   that time, unit-state.yaml does not change, so the Auto-select button has nothing to track and the
   GUI shows stale state.

3. **Exit codes only captured for GUI-initiated applies.** `apply_unit()` writes
   `/tmp/homelab_gui_apply_*.exit`, but wave-runner applies and manual `terragrunt apply` never produce
   that file. Tier 3 (exit-file consumer) therefore misses most real-world applies.

4. **Expensive Tier 2 validate.** `gsutil ls -l -r` over all `_stack/` directories is the only way to
   get authoritative status after a non-GUI apply. Users have to click "Validate (GCS)" manually.

---

## Design: Three-Layer Fix

### Layer A — Generic exit-status hook in root.hcl (fixes problems 1 & 3)

Add a `terraform {}` block to `root.hcl` with two `after_hook` entries on every `apply` and
`destroy`. Terragrunt evaluates hooks in definition order; `run_on_error = false` hooks run only on
success, while `run_on_error = true` hooks always run. This gives a clean ok/fail signal:

```hcl
# root.hcl — add this block (currently has no terraform {} block)
terraform {
  # Step 1: on success, drop a marker before the write hook fires.
  after_hook "exit_status_mark_ok" {
    commands     = ["apply", "destroy"]
    execute      = ["touch", "/tmp/tg-ok-${local._rel_path_full}"]
    run_on_error = false   # skipped on error — marker is absent → hook B writes "fail"
  }

  # Step 2: always write exit-status YAML; reads marker to determine ok vs fail.
  after_hook "exit_status_write" {
    commands     = ["apply", "destroy"]
    execute      = [
      "${get_repo_root()}/utilities/tg-scripts/write-exit-status/run",
      local.rel_path,
      local._rel_path_full,
    ]
    run_on_error = true    # runs even on error; hook A's marker tells it the outcome
  }
}
```

**`utilities/tg-scripts/write-exit-status/run`** (new script):
```bash
#!/usr/bin/env bash
# write-exit-status/run  <unit_path>  <rel_path_full>
# Called by root.hcl after_hook on every apply/destroy.
# Reads the marker file left by exit_status_mark_ok to determine ok vs fail.
set -euo pipefail
source "$(git rev-parse --show-toplevel)/set_env.sh"

UNIT_PATH="$1"
REL_FULL="$2"
STATUS_DIR="${_DYNAMIC_DIR}/unit-status"
MARKER="${STATUS_DIR}/.ok-${REL_FULL}"

mkdir -p "$STATUS_DIR"

if [ -f "$MARKER" ]; then
  STATUS="ok"
  rm -f "$MARKER"
else
  STATUS="fail"
fi

FINISHED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Also clean up any stale maas-status file for this unit now that the apply is done.
rm -f "${STATUS_DIR}/maas-${REL_FULL}.yaml"

# Atomic write (temp + rename)
TMP=$(mktemp "${STATUS_DIR}/.XXXXXX")
cat > "$TMP" <<EOF
unit_path: ${UNIT_PATH}
status: ${STATUS}
finished_at: ${FINISHED_AT}
EOF
mv -f "$TMP" "${STATUS_DIR}/exit-${REL_FULL}.yaml"
```

**The marker file** (`exit_status_mark_ok` hook) also moves to `$_DYNAMIC_DIR/unit-status/`:
```hcl
after_hook "exit_status_mark_ok" {
  commands     = ["apply", "destroy"]
  execute      = [
    "bash", "-c",
    "source $(git rev-parse --show-toplevel)/set_env.sh && mkdir -p $_DYNAMIC_DIR/unit-status && touch $_DYNAMIC_DIR/unit-status/.ok-${local._rel_path_full}"
  ]
  run_on_error = false
}
```

**What this gives us:**
- Every apply/destroy in every context (GUI, wave runner, `make`, manual `tg apply`) produces an
  exit-status YAML under `$_DYNAMIC_DIR/unit-status/exit-<unit>.yaml`.
- All status files live in one directory — no `/tmp/` scatter, no conflicts between repo instances
  (each checkout has its own `config/tmp/dynamic/`).
- Status is derived from the actual terraform exit code, not resource count — a timed-out commission
  that writes zero resources is correctly flagged as `fail`.
- No GCS call required for the ok/fail determination.
- On apply completion, stale maas-status files for that unit are cleaned up automatically.

---

### Layer B — GUI Tier 1: consume exit-status YAMLs, remove GCS cat (fixes problem 1 & 3)

**Current Tier 1 flow:**
```
local tfstate mtime changed → gsutil cat GCS state → parse resource count → write unit-state
```

**New Tier 1 flow:**
```
$_DYNAMIC_DIR/unit-status/exit-*.yaml appeared → read YAML → write unit-state (no GCS)
local tfstate mtime changed (no exit YAML yet) → fall back to gsutil cat (rare edge case)
```

Changes to `local_state_watcher` in `homelab_gui.py`:

1. **Add a poll for `$_DYNAMIC_DIR/unit-status/exit-*.yaml`** (same interval as current, 8 s normal
   / 2 s accelerated). The GUI reads `_DYNAMIC_DIR` from `os.environ["_DYNAMIC_DIR"]`; fall back to
   `<repo_root>/config/tmp/dynamic` if unset.
2. **On each exit-status YAML found:**
   - Read `unit_path`, `status`, `finished_at` from YAML.
   - Write to `unit-state.yaml`: `status`, `last_apply_at = finished_at`.
   - Delete the consumed file (one-shot, same as the existing `.exit` file mechanism).
3. **Retire the existing `/tmp/homelab_gui_apply_*.exit` mechanism** once the root.hcl hook is
   deployed (the hook supersedes it for all apply contexts). Keep the exit-file reader as a
   fallback for a transitional period.
4. **GCS cat in Tier 1 becomes a fallback only:** only triggered when a local tfstate mtime change is
   detected but no exit-status YAML appeared within the same poll cycle. This handles old-format
   applies that predate the hook.

Expected result: Tier 1 GCS calls drop from O(N changed units) per poll cycle to ~0 for normal
operation. GCS is accessed only by Tier 2 validate (on demand) and the rare fallback path.

---

### Layer C — MaaS intermediate status during long-running phases (fixes problem 2)

**Goal:** the GUI sees live progress during commissioning and deployment, giving the Auto-select
button something to track every poll cycle.

#### C1: scripts write a maas-status YAML periodically

The `commission-and-wait` script (and equivalent deploy/gate scripts) write a status file on every
poll iteration (every ~30 s) into the **same** `$_DYNAMIC_DIR/unit-status/` directory:

```
$_DYNAMIC_DIR/unit-status/maas-<rel_path_full>.yaml
```

Using a filename prefix (`exit-` vs `maas-`) keeps both types in one directory without collision.
`$_DYNAMIC_DIR` is set by `set_env.sh` (`config/tmp/dynamic/` relative to the repo root), so each
checkout has its own isolated space — no conflicts between running instances.

Schema:
```yaml
unit_path: maas-pkg/_stack/maas/pwy-homelab/machines/ms01-01/commission/ready
phase: commissioning          # commissioning | ready | allocated | deploying | deployed | failed | timeout
message: "Waiting for MaaS commissioning (elapsed: 4m12s, timeout: 20m)"
hostname: ms01-01
machine_id: abc123
started_at: "2026-04-16T09:30:00Z"
updated_at: "2026-04-16T09:34:12Z"
```

Files are **not consumed** — they are read on every Tier 1 poll cycle until the apply completes.
When the exit-status YAML lands (Layer A), `write-exit-status/run` deletes the corresponding
`maas-<unit>.yaml` as part of its cleanup, so the GUI automatically transitions to the final status.

#### C2: GUI Tier 1 picks up maas-status YAMLs

Add a second watcher path to `local_state_watcher`:
- Poll `$_DYNAMIC_DIR/unit-status/maas-*.yaml` each cycle.
- For each file: read fields, write to `unit-state.yaml` as:
  - `maas_phase: <phase>`
  - `maas_message: <message>`
  - `last_apply_at: <updated_at>` (so the Auto-select timestamp advances every 30 s)
- When exit-status YAML for the same unit arrives: clear `maas_phase` / `maas_message`, set final
  `status`.

This means the Auto-select button tracks the currently-running MaaS unit live, updating every poll
cycle during commission and deploy.

#### C3: MaaS TF module outputs for final exit status

Add `exit_status` and `exit_details` outputs to each `maas_lifecycle_*` module:

```hcl
# infra/maas-pkg/_modules/maas_lifecycle_commission/outputs.tf
output "exit_status" {
  description = "ok | fail | timeout"
  value       = null_resource.commission_trigger.triggers["exit_status"]
}
output "exit_details" {
  description = "Human-readable reason for exit_status"
  value       = null_resource.commission_trigger.triggers["exit_details"]
}
```

The commission-and-wait script writes its exit status into the null_resource trigger so it lands in
GCS state. This makes Tier 2 validate show accurate detail for historical applies, not just "ok
because resources > 0."

---

## unit-state.yaml Schema v2

Drop `resources_count` (it was only ever populated by Tier 2 validate, which is now the only GCS
path; the field added noise without actionable meaning). All other existing fields are kept.

```yaml
schema_version: 2           # bump from 1
units:
  <unit_path>:
    # retained fields
    status: ok              # ok | fail | destroyed | unknown | none
    last_apply_at: "…"      # timestamp of last detected apply/destroy completion
    last_apply_exit_code: 0 # 0 = ok, 1 = fail (kept for tooling compat)
    last_validated_at: "…"  # timestamp of last Tier 2 GCS validate
    # new fields
    details: ""             # human-readable reason from exit-status YAML or MaaS status
    maas_phase: ""          # commissioning | ready | … | "" (cleared on final status)
    maas_message: ""        # live progress message from MaaS script; "" when idle
    maas_hostname: ""       # populated during MaaS intermediate status
```

`resources_count` is removed from all write paths and from the hover popup display.

---

## Files to Create / Modify

| File | Change |
|------|--------|
| `root.hcl` | Add `terraform {}` block with two `after_hook` entries |
| `utilities/tg-scripts/write-exit-status/run` | New script — writes `/tmp/tg-exit-status/<unit>.yaml` |
| `infra/maas-pkg/_modules/maas_lifecycle_commission/outputs.tf` | Add `exit_status`, `exit_details` outputs |
| `infra/maas-pkg/_modules/maas_lifecycle_ready/outputs.tf` | Same |
| `infra/maas-pkg/_modules/maas_lifecycle_allocate/outputs.tf` | Same |
| `infra/maas-pkg/_modules/maas_lifecycle_deploy/outputs.tf` | Same |
| `infra/maas-pkg/_modules/maas_lifecycle_deployed/outputs.tf` | Same |
| `infra/maas-pkg/_tg_scripts/maas/commission-and-wait/run` | Write `/tmp/tg-maas-status/<unit>.yaml` every poll cycle |
| (deploy/gate equivalent) | Same pattern for deploy and gate scripts |
| `homelab_gui.py` — `local_state_watcher` | Consume exit-status YAMLs; consume maas-status YAMLs; GCS cat becomes fallback |
| `homelab_gui.py` — `_write_unit_state` | Add `maas_phase`, `maas_message`, `maas_hostname`, `details`; remove `resources_count` write |
| `homelab_gui.py` — hover popup | Display `maas_phase`, `maas_message`, `details` if non-empty; remove `resources_count` display |
| `homelab_gui.py` — Tier 2 validate | Remove `resources_count` from write path and status display |
| `homelab_gui.py` — `apply_unit()` | Keep `.exit` file write running in parallel with new hook mechanism indefinitely |
| `docs/de3-gui-pkg/_docs/gui-build-status.md` | Update schema and tier descriptions |

---

## Decisions

1. **`destroy` writes exit status** — yes. The hook design already covers `["apply", "destroy"]`.
   On successful destroy the GUI immediately sets `status: destroyed`; on failed destroy it sets
   `status: fail`. No more waiting for Tier 2 validate to notice a missing GCS state file.

2. **Transitional period for `/tmp/homelab_gui_apply_*.exit`** — keep both readers running in
   parallel indefinitely until there is a concrete reason to drop the old path. The old mechanism
   costs nothing to maintain and provides a safety net if the root.hcl hook isn't present on older
   checkouts.

3. **`resources_count` removed** — dropped from all write paths and from the GUI. See schema v2
   above.

## Remaining Open Questions

4. **Wave runner context** — the `run` script calls `terragrunt run --all apply`. Confirm that
   root.hcl `after_hook` fires for each unit in a `run --all` (it does — hooks run per-unit, so
   this should work; verify with a test apply before full rollout).

5. **`/tmp/tg-maas-status/` stale files** — these persist across reboots in theory (though /tmp is
   usually cleared). Should the root.hcl hook's write-exit-status script also delete any stale
   maas-status file for the same unit when the apply completes? Suggested answer: yes — clean up in
   the write-exit-status script so the GUI doesn't show stale MaaS phase after the apply is done.

---

## Implementation Order

1. **Layer A** (root.hcl hook + write-exit-status script) — standalone, no GUI changes needed.
   After this lands, exit-status YAMLs appear in `/tmp/tg-exit-status/` for every apply.

2. **Layer B** (GUI Tier 1: consume exit-status YAMLs, retire GCS cat) — depends on Layer A.
   After this lands, Tier 1 GCS calls go to zero for normal operation.

3. **Layer C1+C2** (MaaS intermediate status: script writes + GUI picks up) — parallel to Layer B;
   depends on commission-and-wait and deploy scripts being updated.

4. **Layer C3** (MaaS TF outputs) — lowest priority; adds historical detail to Tier 2 validate but
   doesn't affect real-time tracking.
