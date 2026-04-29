# unit-mgr — Unit Rename / Move / Copy Framework Tool

## Purpose

`framework/unit-mgr/run` is a Python CLI that moves, copies, or renames Terragrunt unit
trees in this lab framework. It handles all four things that must stay in sync when a unit
path changes:

1. The filesystem directory (the `terragrunt.hcl` + any sibling files)
2. `config_params` keys in the owning package YAML (`infra/<pkg>/_config/<pkg>.yaml`)
3. `config_params` keys in the owning SOPS secrets file (`infra/<pkg>/_config/<pkg>_secrets.sops.yaml`)
4. GCS Terraform state blobs (`gs://<bucket>/<rel_path>/default.tfstate`)

It also scans the entire repo for `dependencies { paths = [...] }` references that point into
the moved tree, and reports any that fall **outside** the moved tree (those won't be
auto-updated and need manual attention).

Cross-package moves are fully supported. Moving a unit from `demo-buckets-example-pkg` to
`pwy-home-lab-pkg` migrates config_params and secrets between the two packages' files.

---

## CLI Usage

```
./framework/unit-mgr/run <command> <src-rel-path> <dst-rel-path> [options]
```

Paths are relative to `infra/` — e.g. `demo-buckets-example-pkg/_stack/gcp/examples/storage-bucket`.

### Commands

| Command | Effect |
|---------|--------|
| `copy`  | Duplicate the tree; source is preserved |
| `move`  | Relocate the tree; source is deleted after all other steps succeed |

`rename` is just `move` where the destination is the same parent with a different leaf name.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | off | Print every action that would be taken; execute nothing |
| `--json-report` | off | Write a JSON report to stdout at the end (consumed by the GUI Refactor panel) |
| `--skip-state` | off | Skip GCS state migration. **Only safe for units that have never been applied.** For `move`, if GCS state exists the tool will print a warning — the source directory is deleted but state is left behind at the old GCS path |
| `--skip-secrets` | off | Skip SOPS secrets migration |

### Examples

```bash
# Rename a single leaf unit (same parent directory)
./framework/unit-mgr/run move \
  pwy-home-lab-pkg/_stack/gcp/us-central1/dev/old-bucket \
  pwy-home-lab-pkg/_stack/gcp/us-central1/dev/new-bucket

# Move an entire subtree to a new parent
./framework/unit-mgr/run move \
  pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-01 \
  pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-01-renamed

# Copy example units from demo package into the live package (test scenario)
./framework/unit-mgr/run copy \
  demo-buckets-example-pkg/_stack/gcp/examples \
  pwy-home-lab-pkg/_stack/gcp/us-central1/dev/demo-copy

# Dry-run first to see what would change
./framework/unit-mgr/run move --dry-run --json-report \
  demo-buckets-example-pkg/_stack/aws/examples \
  pwy-home-lab-pkg/_stack/aws/us-east-1/dev/demo-copy
```

---

## File Layout

```
framework/unit-mgr/
  run                          # bash entry point — sources set_env.sh, activates venv, invokes main.py
  requirements.txt             # pyyaml, google-cloud-storage
  README.md                    # this document
  unit_mgr/
    __init__.py
    main.py                    # argparse CLI; orchestrates the operation phases
    unit_tree.py               # walk a directory subtree, collect all unit dirs (has terragrunt.hcl)
    config_yaml.py             # read / write config_params keys in package YAML files (ruamel.yaml)
    sops_secrets.py            # read / write config_params keys in SOPS-encrypted secrets files
    gcs_state.py               # migrate GCS state blobs and lock files
    dependency_scanner.py      # scan all .hcl files for dependency path references
    report.py                  # build human-readable log lines and JSON report structure
```

The `run` script follows the same pattern as `framework/generate-ansible-inventory/run`:
- sources `set_env.sh`
- calls `_activate_python_locally "$SCRIPT_DIR"` to create/reuse a `.venv`
- then delegates to `python3 -m unit_mgr.main "$@"` (run as a package so relative imports resolve)

---

## Operation Phases

All phases run in order. `--dry-run` prints what each phase would do without executing.
Any phase failure aborts the run; no partial state is left (see rollback note below).

### Phase 0 — Pre-flight checks

- `src` absolute path exists under `infra/`
- `dst` absolute path does NOT yet exist
- Framework backend is `gcs` (read from `config/framework.yaml`); fail clearly if not
- No `.tflock` files exist at any GCS state path under `src` — fail if locked (unit is in-flight)
- Read GCS bucket name from `config/framework.yaml`

### Phase 1 — Unit discovery

Walk the `src` directory tree. A **unit** is any directory that contains a `terragrunt.hcl`
file. Collect a list of `UnitInfo` objects:

```python
@dataclass
class UnitInfo:
    src_abs: Path          # absolute filesystem path
    dst_abs: Path          # where it will go
    src_rel: str           # relative to infra/ — used as config_params key and GCS prefix
    dst_rel: str           # the renamed version of src_rel
    gcs_state_src: str     # gs://bucket/src_rel/default.tfstate
    gcs_state_dst: str     # gs://bucket/dst_rel/default.tfstate
```

If `src` is itself a leaf unit (has `terragrunt.hcl`), the list contains exactly one entry.
If `src` is a folder, the list contains all descendant leaf units.

### Phase 2 — Dependency scan

Scan every `terragrunt.hcl` in the entire `infra/` tree. For each file, extract any paths
listed inside `dependencies { paths = [...] }` blocks (regex/string scan — no HCL parser
required; paths are always string literals containing `get_repo_root()`).

Classify each reference that points at a unit in the `src` tree:

| Category | Description | Action |
|----------|-------------|--------|
| **Internal** | Reference is from a file inside `src` tree, to a unit also inside `src` tree | Will be auto-updated in Phase 4b |
| **External inbound** | Reference is from a file **outside** `src` tree, to a unit **inside** `src` tree | **Report as warning** — the referencing file won't be auto-patched |

External inbound warnings are the key output of this phase. They appear in the log, and in the
JSON report consumed by the GUI Refactor panel.

### Phase 3 — Package detection

```python
src_pkg = src_rel_path.split("/")[0]   # e.g. "demo-buckets-example-pkg"
dst_pkg = dst_rel_path.split("/")[0]   # e.g. "pwy-home-lab-pkg"
is_cross_package = src_pkg != dst_pkg
```

Locate the public config YAML and secrets SOPS file for each package:

```
src public:   infra/<src_pkg>/_config/<src_pkg>.yaml
src secrets:  infra/<src_pkg>/_config/<src_pkg>_secrets.sops.yaml  (may not exist)
dst public:   infra/<dst_pkg>/_config/<dst_pkg>.yaml
dst secrets:  infra/<dst_pkg>/_config/<dst_pkg>_secrets.sops.yaml  (may not exist — will be created)
```

### Phase 4 — Execute

#### 4a — Directory copy/move

```python
shutil.copytree(src_abs, dst_abs)
```

After copy, delete all `.terragrunt-cache/` directories found anywhere under `dst_abs`.
These directories contain absolute paths baked in during the last `terragrunt init`; they must
be regenerated at the new path.

For `move`, `shutil.rmtree(src_abs)` runs **last** (after all other sub-phases succeed).

#### 4b — Patch internal dependency references

In every `terragrunt.hcl` under `dst_abs`, replace all occurrences of `src_rel_path` with
`dst_rel_path`. This is a plain string substitution — no HCL parser needed. The replacement
preserves `get_repo_root()` calls and path separators.

Example replacement in a `dependencies` block:
```
"${get_repo_root()}/infra/pwy-home-lab-pkg/_stack/null/pwy-homelab/old-unit"
→
"${get_repo_root()}/infra/pwy-home-lab-pkg/_stack/null/pwy-homelab/new-unit"
```

#### 4c — Migrate public config_params

Load the source package YAML using `ruamel.yaml` (to preserve comments and formatting).
Navigate to `<pkg>.config_params` (if present).

Find all keys whose string value starts with `src_rel_path`. For each:
- Compute `new_key = dst_rel_path + old_key[len(src_rel_path):]`
- Insert the entry under `new_key` (preserving order relative to surrounding keys)
- Delete the old key

If `is_cross_package`:
- Write modified src YAML back (key removed)
- Load dst YAML, insert keys there, write dst YAML back

If same-package:
- Write modified YAML once (keys renamed in place)

`ruamel.yaml` is used to avoid destroying comments and block style in the YAML file.
Fall back to standard `pyyaml` only if `ruamel.yaml` is unavailable.

#### 4d — Migrate SOPS secrets

```
NEVER use shell redirect (>) or the Write tool on .sops.yaml files.
Use sops --encrypt --output <file> for re-encryption (atomic write).
```

If the source secrets file does not exist: skip silently.

```python
# 1. Decrypt source to memory
result = subprocess.run(["sops", "--decrypt", src_sops_path],
                        capture_output=True, text=True, check=True)
src_data = yaml.safe_load(result.stdout)

# 2. Extract keys that match src_rel_path prefix
config_params = src_data.get(f"{src_pkg}_secrets", {}).get("config_params", {})
keys_to_move = {k: v for k, v in config_params.items()
                if k == src_rel_path or k.startswith(src_rel_path + "/")}
if not keys_to_move:
    # nothing to migrate
    return

# 3. Rename keys
moved = {dst_rel_path + k[len(src_rel_path):]: v for k, v in keys_to_move.items()}

# 4. Remove from source data (in-memory)
for k in keys_to_move:
    del config_params[k]

# 5. Re-encrypt source (or skip for copy operation — source is unchanged)
if operation == "move":
    _sops_encrypt_from_dict(src_sops_path, src_data)

# 6. Merge into destination data
if dst_sops_path.exists():
    result = subprocess.run(["sops", "--decrypt", dst_sops_path],
                            capture_output=True, text=True, check=True)
    dst_data = yaml.safe_load(result.stdout)
else:
    dst_data = {f"{dst_pkg}_secrets": {"config_params": {}}}

dst_config_params = dst_data[f"{dst_pkg}_secrets"].setdefault("config_params", {})
dst_config_params.update(moved)
_sops_encrypt_from_dict(dst_sops_path, dst_data)
```

`_sops_encrypt_from_dict` writes to a tempfile then calls:
```bash
sops --encrypt --output "$SOPS_FILE" /tmp/tmpXXXXXX.yaml
rm /tmp/tmpXXXXXX.yaml
```

#### 4e — Migrate GCS state (unless `--skip-state`)

For each `UnitInfo` in the tree:

1. Check if `gcs_state_src` exists: `gsutil -q stat gs://...` (exit 0 = exists)
2. If it exists:
   - `gsutil cp gcs_state_src gcs_state_dst`
   - For `move`: `gsutil rm gcs_state_src`
3. Check for a `.tflock` at the src path — if found and this is `move`, delete it

State files that don't exist (unit was never applied) are silently skipped. This is the normal
case for example/skeleton units that are being copied as templates.

#### 4f — Delete source (move only)

```python
shutil.rmtree(src_abs)
```

Only runs after all other phases succeed.

### Phase 5 — Report

Human-readable log is always written to stdout. With `--json-report`, a JSON object is also
written to stdout (after all other output, separated by a sentinel line `---JSON---`):

```json
{
  "operation": "move",
  "src": "demo-buckets-example-pkg/_stack/gcp/examples",
  "dst": "pwy-home-lab-pkg/_stack/gcp/us-central1/dev/demo",
  "dry_run": false,
  "units_found": 3,
  "config_keys_migrated": 4,
  "secret_keys_migrated": 1,
  "state_files_migrated": 2,
  "state_files_skipped": 1,
  "external_deps": [
    {
      "hcl_file": "infra/pwy-home-lab-pkg/_stack/null/pwy-homelab/configure/terragrunt.hcl",
      "line": 12,
      "old_ref": "demo-buckets-example-pkg/_stack/gcp/examples/storage-bucket",
      "new_ref": "pwy-home-lab-pkg/_stack/gcp/us-central1/dev/demo/storage-bucket",
      "action": "manual_update_required"
    }
  ],
  "errors": []
}
```

---

## GUI Integration — Refactor Panel

### Entry point

A **"Refactor"** option is added to the right-click context menu on **folder nodes** in the
infra tree (non-leaf nodes only — i.e. nodes that do not have a `terragrunt.hcl`).
Right-clicking a folder and selecting "Refactor":

1. Pre-fills `refactor_src_path` with that folder's rel-path
2. Switches the top-right panel to `"refactor"` mode

Leaf units (nodes that are themselves a single Terragrunt unit) are also supported — the tool
handles a single-unit tree just as well as a multi-unit subtree. The context menu entry appears
on both folders and leaf units.

### Panel layout

The top-right panel gains a third mode tab: **Params | Waves | Refactor**.

```
┌─────────────────────────────────────────────────────┐
│ [Params] [Waves] [Refactor]                         │
├─────────────────────────────────────────────────────┤
│ Operation:  ○ Copy  ● Move                          │
│                                                     │
│ Source:                                             │
│   demo-buckets-example-pkg/_stack/gcp/examples      │  (read-only, from selected node)
│                                                     │
│ Destination:                                        │
│   [                                               ] │  (text input)
│                                                     │
│ [  Preview  ]                                       │
├─────────────────────────────────────────────────────┤
│ Preview results:                                    │
│                                                     │
│  Units to process (3):                              │
│    • .../examples/storage-bucket                    │
│    • .../examples/logging-bucket                    │
│    • .../examples/archive-bucket                    │
│                                                     │
│  ⚠ External dependencies (1) — update manually:    │
│    configure/terragrunt.hcl:12                      │
│      refs: .../examples/storage-bucket              │
│                                                     │
│  State files: 0 to migrate (units not yet applied)  │
│  Config keys: 3 public, 0 secrets                   │
│                                                     │
│ [  Execute  ]                                       │
└─────────────────────────────────────────────────────┘
```

### Interaction flow

1. User right-clicks a node → selects "Refactor" → panel opens in Refactor mode
2. User selects Copy or Move
3. User types destination path
4. User clicks **Preview**:
   - GUI calls `unit-mgr --dry-run --json-report <op> <src> <dst>` via subprocess
   - Parses JSON from stdout (after `---JSON---` sentinel)
   - Renders unit list, warnings, and counts in the panel
5. User reviews warnings (external deps listed here are the ones requiring manual `.hcl` edits)
6. User clicks **Execute**:
   - GUI calls `unit-mgr --json-report <op> <src> <dst>` (no `--dry-run`)
   - Terminal panel (bottom-right) is opened to show live output
   - On completion, JSON report is parsed and the result summary is shown in the Refactor panel
   - Infra tree is reloaded to reflect new paths

### State variables added to AppState

```python
refactor_operation: str = "move"                      # "copy" or "move"
refactor_src_path: str = ""                           # pre-filled from selected node
refactor_dst_path: str = ""                           # user types this
refactor_preview_result: dict = {}                    # parsed JSON from --dry-run
refactor_preview_external_deps: list[dict] = []       # external_deps list from preview
refactor_running: bool = False                        # True while execute is in progress
refactor_result: dict = {}                            # parsed JSON from actual run
refactor_error: str = ""                              # non-empty if run failed
```

---

## Copy/Move Mechanism

The Refactor panel (calling `unit-mgr`) is the sole copy/move mechanism. The older
clipboard-based copy/paste has been removed. `unit-mgr` handles all cases: single unit,
subtree, same-package, cross-package, with and without existing GCS state.

---

## Rollback Behaviour

`unit-mgr` does not implement automatic rollback. Operations are designed to fail-fast
before any mutation:

- Phase 0 checks for locks before touching anything
- The filesystem copy happens before any YAML or state mutation, so if YAML/state fails, the
  dst directory can be manually deleted and nothing is corrupted
- GCS state migration is the last destructive action for `move` (src state deleted only after
  dst state is confirmed written via `gsutil stat`)
- SOPS re-encryption uses `sops --encrypt --output` (atomic write — either succeeds or the
  original file is intact)
- Config YAML writes use `.tmp` + `os.replace()` (atomic write — truncation on crash is not
  possible)

**`--skip-state` exception:** for `move`, if `--skip-state` is passed and GCS state exists,
the source directory is deleted in Phase 4f but the state at the old GCS path is left behind.
This is flagged as a warning in the output. Recovery: `gsutil cp -r gs://bucket/old/ gs://bucket/new/` then `gsutil rm -r gs://bucket/old/`.

In the unlikely event of a partial failure mid-run, the log output will identify exactly which
steps completed. Recovery is: delete dst directory, re-run with `--skip-state` if state was
already migrated.

---

## Backend Support

Only **GCS** (`backend.type: gcs` in `config/framework.yaml`) is supported. The tool will
fail clearly at Phase 0 if the backend is anything else. S3 and Azure Blob are not supported.

---

## Known Constraints

- Moving a unit while it is actively locked (`.tflock` on GCS) will fail at Phase 0. Wait for
  the apply to complete, or manually delete the stale lock, before renaming.
- The `sops` CLI must be on `PATH` and configured with the correct key (age or GCP KMS) for
  SOPS operations to succeed.
- `gsutil` must be on `PATH` and authenticated (via `gcloud auth application-default login`)
  for GCS state operations.
- If the destination package YAML doesn't yet exist, the tool will fail. Create the package
  structure first (at minimum an empty `infra/<dst_pkg>/_config/<dst_pkg>.yaml`).

---

## Reflex GUI Constraints

These apply to all code added to `homelab_gui.py`. Violating them causes silent failures or
startup errors that are hard to diagnose.

### Event handler names must be public (no leading underscore)

Reflex does not register methods whose names start with `_` as events. Using such a method as
a callback argument causes a runtime error.

```python
# WRONG — Reflex won't register this; breaks if used as callback=
def _set_refactor_dst(self, v: str): ...

# CORRECT
def set_refactor_dst(self, v: str): ...
```

### Background tasks: use `@rx.event(background=True)`, not `@rx.background`

`rx.background` does not exist in Reflex 0.8.27. Background task methods must also be public.

```python
# WRONG
@rx.background
async def run_unit_mgr(self): ...

# CORRECT
@rx.event(background=True)
async def run_unit_mgr(self): ...
```

### `rx.call_script` callbacks receive one scalar only

Callbacks receive a single int, float, str, or bool. Do not return a JS object. If two values
are needed, make two separate `rx.call_script` calls with two separate public handlers.

### No Python string concatenation with Reflex vars

Inside `rx.foreach` component functions, `node["field"]` is a Reflex `ObjectItemOperation`,
not a Python string. Use separate children, not `+`:

```python
# WRONG
rx.text("(" + node["wave"] + ")")

# CORRECT
rx.text("(", node["wave"], ")")
```

