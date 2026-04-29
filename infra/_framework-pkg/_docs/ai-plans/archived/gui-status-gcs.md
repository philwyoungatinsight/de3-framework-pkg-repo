# Plan: GCS-native Unit & Wave Status

## Problem with the current design

1. **`unit-state.yaml` is machine-local.** If the GUI host is rebuilt, or the wave runner runs on a different machine, status is lost and a full GCS validate scan is needed to recover.
2. **Tier 1 (`.terragrunt-cache` scan) is slow, wasteful, and fragile.** It polls the entire `infra/` tree every 8 s looking for tfstate mtime changes, fires a `gsutil cat` per changed unit, and races with in-progress applies. Once Tier 0 covers all apply paths this scan adds no value.
3. **MaaS lifecycle fields (`maas_phase`, `maas_message`, `maas_hostname`) pollute unit status.** Unit status should be `ok | fail | destroyed | unknown | none`. Live MaaS progress is a separate concern.

---

## GCS bucket layout

```
gs://de3-tfstate/
│
├── maas-pkg/                                       ─┐
│   └── _stack/maas/pwy-homelab/                    │
│       ├── config/                                  │
│       │   └── default.tfstate                      │  existing TF state
│       └── machines/                                │  (unchanged)
│           ├── de3-bmc/default.tfstate              │
│           └── de3-nuc-1/default.tfstate           ─┘
│
├── proxmox-pkg/
│   └── _stack/proxmox/pwy-homelab/
│       └── vms/pve-1/
│           └── k8s-node-1/default.tfstate          ─── existing TF state
│
├── unit_status/                                    ─┐
│   ├── maas-pkg/_stack/maas/pwy-homelab/           │
│   │   ├── config/                                  │
│   │   │   ├── 2026-04-14T09-00-00Z.json           │  oldest (purged by script)
│   │   │   ├── 2026-04-15T14-22-10Z.json           │
│   │   │   └── 2026-04-18T08-45-33Z.json           │  newest ← reader takes this
│   │   └── machines/                                │
│   │       ├── de3-bmc/                             │
│   │       │   ├── 2026-04-17T11-10-05Z.json       │  append-only; keep last N
│   │       │   └── 2026-04-18T08-46-01Z.json       │
│   │       └── de3-nuc-1/                           │
│   │           └── 2026-04-18T09-02-44Z.json       │
│   └── proxmox-pkg/_stack/proxmox/pwy-homelab/     │
│       └── vms/pve-1/k8s-node-1/                   │
│           └── 2026-04-18T07-30-12Z.json           ─┘
│
└── wave_status/                                    ─┐
    ├── on_prem.maas.config/                         │
    │   ├── 2026-04-18T08-44-00Z.json               │  phase=apply  status=running
    │   └── 2026-04-18T08-45-10Z.json               │  phase=apply  status=ok
    ├── on_prem.maas.machines/                       │  append-only; keep last N
    │   ├── 2026-04-18T08-46-00Z.json               │  phase=apply  status=running
    │   ├── 2026-04-18T08-48-30Z.json               │  phase=apply  status=ok
    │   ├── 2026-04-18T08-48-31Z.json               │  phase=test   status=running
    │   └── 2026-04-18T08-49-05Z.json               │  phase=test   status=ok
    └── on_prem.proxmox.vms/                         │
        └── 2026-04-18T07-28-00Z.json               ─┘  (wave ran earlier today)
```

`<ts>` is an ISO-8601 UTC timestamp with colons replaced by hyphens for GCS key
compatibility: `2026-04-14T10-15-36Z`.

### Why timestamped files, not a single `latest.json`

- **No overwrite of existing records.** Each write is a new GCS object at a unique key.
  GCS PUT for a new key is atomic; there is no read-modify-write.
- **Concurrent-wave safe.** Two waves running simultaneously write to different unit paths
  and different wave names — entirely different GCS keys, zero contention.
- **History preserved.** The last N events are visible in the bucket without extra tooling.
- **Readers take the lexicographically last key** (`gsutil ls unit_status/<path>/` and pick
  the last entry — ISO timestamps sort correctly as strings).

---

## File schemas

### `unit_status/<unit_path>/<ts>.json`

```json
{
  "unit_path": "maas-pkg/_stack/maas/pwy-homelab/machines/de3-bmc",
  "status": "ok",
  "last_apply_exit_code": 0,
  "finished_at": "2026-04-14T10:15:36Z",
  "details": "",
  "writer": "write-exit-status"
}
```

Status values: `ok | fail | destroyed`

`writer` identifies the source (`write-exit-status`, `gui-apply`) for debugging.

### `wave_status/<wave_name>/<ts>.json`

```json
{
  "wave_name": "on_prem.maas.machines",
  "phase": "test-playbook",
  "status": "ok",
  "started_at": "2026-04-14T10:00:00Z",
  "finished_at": "2026-04-14T10:15:36Z",
  "units_total": 4,
  "units_ok": 4,
  "units_fail": 0
}
```

Status values: `running | ok | fail`
Phase values: `apply | inventory | precheck | test-playbook`

One object is written when a phase **starts** (`status: running`, no `finished_at`) and
one when it **ends** (`status: ok | fail`). The GUI reads the last object to know current
phase and outcome.

---

## Writers

| Event | Writer | GCS path |
|-------|--------|----------|
| Unit apply/destroy completes | `write-exit-status/run` (root.hcl after-hook) | `unit_status/<unit_path>/<ts>.json` |
| GUI `apply_unit()` completes | GUI backend | `unit_status/<unit_path>/<ts>.json` |
| Wave phase starts | wave runner (`run`) | `wave_status/<wave_name>/<ts>.json` (`running`) |
| Wave phase ends | wave runner (`run`) | `wave_status/<wave_name>/<ts>.json` (`ok\|fail`) |

All unit/wave writes are fire-and-forget (`gsutil cp ... &`) — they must not block
the terragrunt apply or wave runner exit.

GCS auth: `GOOGLE_APPLICATION_CREDENTIALS` is already set by `root.hcl` for TF; `gsutil`
picks it up automatically. No extra wiring needed.

---

## Readers

### Two distinct purposes — do not conflate

GCS status objects serve **persistence and cross-machine sharing**, not real-time GUI
display. The local file paths (exit-*.yaml, run.log, unit-state.yaml) remain the fast
path for the GUI. This distinction drives every read decision below.

| Object | Real-time GUI? | Persistence / cross-machine / CI? |
|--------|---------------|----------------------------------|
| `unit_status/` | No — local `exit-*.yaml` → `unit-state.yaml` is faster | Yes — read on GUI load to recover after rebuild |
| `wave_status/` | No — `run.log` on disk is faster when runner and GUI share a machine | Yes — read on GUI load to recover wave history; CI pipelines gate on it |

### GUI `local_state_watcher` (simplified — Tier 1 removed)

The watcher continues to use local files for real-time display. New poll cycle (every 8 s):

1. **Tier 0**: consume `$_DYNAMIC_DIR/unit-status/exit-*.yaml` → write GCS `unit_status/` entry + local `unit-state.yaml`
2. **Tier 0b (MaaS)**: read `$_DYNAMIC_DIR/unit-status/maas-*.yaml` (don't consume) → local display only; no GCS write
3. **Tier 3**: consume `$_GUI_DIR/homelab_gui_apply_*.exit` → write GCS `unit_status/` entry + local `unit-state.yaml`

**Tier 1 (`.terragrunt-cache` scan) is removed entirely.**

### GUI on-load — incremental GCS sync (background)

Both `unit_status/` and `wave_status/` are synced on startup as background async jobs.
The sequence:

```
1. Read local unit-state.yaml immediately (no network, populates UI at startup)
2. Background job A: gsutil ls -l unit_status/ → pull objects newer than last sync
   → merge into unit-state.yaml + unit_build_statuses Reflex state
3. Background job B: gsutil ls -l wave_status/ → pull last object per wave name
   → merge into wave_statuses Reflex state (recovers wave history from before this session)
4. After each sync: update unit_status_sync_after / wave_status_sync_after timestamps
```

Jobs A and B run concurrently. Neither blocks the UI — the local YAML has already
populated it in step 1. Purpose: recover state written by a wave runner on another
machine, or by a previous session before the GUI started. Not a poll loop.

The validate button triggers a full re-sync of both prefixes (ignores mtime cache).

### GUI waves panel — keep `run.log` for real-time; GCS for recovery

The waves panel continues to parse `run.log` for real-time wave status during an active
run — a local disk read with no network overhead.

The on-load GCS sync (background job B above) populates historical wave state for waves
that completed before this GUI session started. The two sources are merged: `run.log`
wins for any wave currently visible in the log; GCS fills in waves not present in the
current log.

### CI / external consumers — `wave_status/` and `unit_status/`

The primary consumer of GCS status objects outside the GUI:

```bash
# Block a CI step on wave success
latest=$(gsutil ls gs://<bucket>/wave_status/on_prem.maas.machines/ | tail -1)
status=$(gsutil cat "$latest" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
[[ "$status" == "ok" ]] || { echo "wave failed"; exit 1; }

# Check current status of a specific unit
gsutil ls gs://<bucket>/unit_status/maas-pkg/_stack/maas/pwy-homelab/machines/de3-bmc/ \
  | tail -1 | xargs gsutil cat
```

### Reading "current status" for a unit

```bash
gsutil ls gs://<bucket>/unit_status/<unit_path>/ | tail -1 | xargs gsutil cat
```

The lexicographically last object is the most recent event. Readers never need to
merge or conflict-resolve.

---

## Concurrency: two waves running simultaneously

Each wave writes to `wave_status/<its-own-wave-name>/`. Each unit apply writes to
`unit_status/<its-own-unit-path>/`. No two concurrent writes ever target the same GCS key
because:

- Wave names are unique per run.
- Unit paths are unique per unit, and the TF DAG ensures a unit is applied by at most one
  wave at a time (wave sequencing rule + explicit `dependencies` blocks).

If the sequencing invariant is ever violated and two waves race on the same unit, the
result is two timestamped objects at slightly different keys — both are preserved,
the later one wins when the reader takes `tail -1`. No corruption, no lost data.

---

## What is removed

| Removed | Replacement |
|---------|------------|
| Tier 1: `.terragrunt-cache` mtime scan | Tier 0 exit-hooks cover all apply paths |
| "Validate (GCS)" full `gsutil ls -l -r` tfstate scan | Incremental `unit_status/` + `wave_status/` sync on load |
| MaaS fields written to `unit-state.yaml` | Remain in local display only (Tier 0b); no GCS equivalent |
| `gcs_state_mtimes` Reflex state var | `unit_status_sync_after` + `wave_status_sync_after` timestamps |

`run.log` parsing in the waves panel is **not** removed — it remains the real-time source
during active runs. GCS `wave_status/` fills in historical waves from before the current session.

---

## Migration

1. `write-exit-status/run` adds a fire-and-forget `gsutil cp` of the status JSON. No root.hcl change.
2. Wave runner (`run`) writes phase start/end objects to `wave_status/`.
3. GUI drops the Tier 1 loop body from `local_state_watcher`; Tier 0b MaaS path unchanged.
4. GUI on-load syncs from `unit_status/` and `wave_status/` as concurrent background jobs.
5. GUI waves panel merges GCS history with live `run.log` data.
6. `unit-state.yaml` schema v2 retained; `maas_*` fields deprecated (left empty, removed later).

No change to the TF state layout. `unit_status/` and `wave_status/` are new prefixes.

---

## Retention / purge

### Why a script, not a GCS lifecycle rule

GCS lifecycle rules can delete objects older than N days but cannot express
"keep the newest object per prefix group." A lifecycle rule on `unit_status/**`
older than 90 days would delete the only record for a unit that hasn't been
touched in 3 months. The purge must be group-aware.

### Purge script: `scripts/human-only-scripts/purge-gcs-status/run`

Invoked automatically as part of `make clean-all` and available to run manually.

**Algorithm:**

```
for prefix in [unit_status, wave_status]:
    list all objects under gs://<bucket>/<prefix>/
    group objects by their parent path
        unit_status: group key = everything before the last /  (= unit_path)
        wave_status: group key = everything before the last /  (= wave_name)
    within each group:
        sort ascending by object name (ISO timestamps sort lexicographically = chronologically)
        keep the last KEEP_LAST objects
        delete all earlier objects
```

**Default:** `KEEP_LAST=5` (keep the 5 most recent status events per unit/wave).
Configurable via env var `_GCS_STATUS_KEEP_LAST`. Set to `1` for minimum footprint.

**Implementation notes:**

- Use `gsutil ls -l gs://<bucket>/unit_status/` with `**` glob to list recursively.
  Parse output to extract object URIs and group by stripping the last path component.
- Deletions are batched: `gsutil -m rm` accepts multiple URIs, parallelises internally.
- Dry-run mode via `DRY_RUN=1`: prints what would be deleted without deleting.
- The script never deletes the newest object in a group — the sort+keep-last logic
  guarantees this regardless of timestamp content (sorting is by object name, not
  by the `finished_at` field inside the JSON).
- Script follows the standard `run` convention: sources `set_env.sh`, reads bucket
  name from `framework.yaml` via Python/jq, exits non-zero on any gsutil error.

**Example output:**

```
unit_status/maas-pkg/_stack/maas/pwy-homelab/machines/de3-bmc: 7 objects, keeping 5, deleting 2
unit_status/proxmox-pkg/_stack/proxmox/pwy-homelab/vms/pve-1/k8s-node-1: 3 objects, keeping 3, deleting 0
wave_status/on_prem.maas.machines: 12 objects, keeping 5, deleting 7
...
Deleted 42 objects (12.3 KB recovered)
```

### Integration with `make clean-all`

Add a call to `purge-gcs-status/run` in the `./run --clean-all` sequence, after TF
destroy completes but before the GCS state bucket wipe. This ensures status history
is trimmed to `KEEP_LAST` entries before the bucket is partially cleared.

If `--clean-all` is wiping the full bucket (nuclear mode), skip the purge — the wipe
handles everything.

### GCS lifecycle rule (defence-in-depth)

Set a 180-day hard-expiry lifecycle rule on the `unit_status/` and `wave_status/` prefixes
as a backstop against the purge script not running. This does NOT replace the script —
it only catches objects that slip through (e.g. a unit with no recent activity where
even the newest object is old). Configure once in the bucket seed script.

### CI / external consumers

With status in GCS, a CI pipeline can gate on wave success:

```bash
latest=$(gsutil ls gs://<bucket>/wave_status/on_prem.maas.machines/ | tail -1)
status=$(gsutil cat "$latest" | jq -r .status)
[[ "$status" == "ok" ]] || exit 1
```

No GUI, no SSH, no local machine access needed.
