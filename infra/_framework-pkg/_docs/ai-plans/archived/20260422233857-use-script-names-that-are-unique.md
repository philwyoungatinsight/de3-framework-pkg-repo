# Plan: Use Unique Script Names for Framework Utility Tools

## Objective

Replace the generic `run` filename with descriptive names for all framework utility
tools that are **not** driven by a sibling `Makefile`. Export each named tool's path
as an env var from `set_env.sh` so any caller (scripts, GUI, future tools) uses the
env var rather than hardcoding a path. Named scripts are discoverable via
`find . -name unit-mgr` and unambiguous in docs and error messages.

## Context

### Naming convention today

| Pattern | Example | Kept? |
|---|---|---|
| Sibling `Makefile` calls `./run` | `_generate-inventory/Makefile` → `./run --build` | Keep `run` |
| No sibling Makefile; called by other scripts | `_git_root/run` line 129: `FRAMEWORK_PKG_DIR / '_framework/_pkg-mgr/run'` | **Rename + env var** |
| No sibling Makefile; invoked directly by humans | `_unit-mgr/run`, `_fw-repo-mgr/run` | **Rename + env var** |
| Per-package hooks discovered by the framework | Framework constructs `infra/<pkg>/_clean_all/run` | Keep `run` (framework convention) |
| tg-scripts called via HCL hook env var | `write-exit-status/run` via `_WRITE_EXIT_STATUS` | **Rename** (env var path updated) |

### Callers of each `run` script today

| Script | Callers |
|---|---|
| `_config-mgr/run` | None automated — human only |
| `_pkg-mgr/run` | `_git_root/run` line 129 (`PKG_MGR` py constant); `_fw-repo-mgr/run` line 12; `homelab_gui.py` line 3035 |
| `_unit-mgr/run` | `homelab_gui.py` line 11252 (hardcoded path) |
| `_ephemeral/run` | `_git_root/run` line 131 (`_EPHEMERAL_RUN` py constant); `_fw-repo-mgr/run` line 7 |
| `_clean_all/run` | `_git_root/run` line 127 (`NUKE_ALL` py constant) |
| `_fw-repo-mgr/run` | Human only |
| `_human-only-scripts/*/run` | Human only |
| `_ai-only-scripts/upgrade-routeros/run` | Human/AI only |
| `_utilities/tg-scripts/write-exit-status/run` | `set_env.sh` line 19 (`_WRITE_EXIT_STATUS`); `root.hcl` line 428 |

### GUI path-hardcoding

`homelab_gui.py` (in `de3-gui-pkg`) constructs framework tool paths directly:
- Line 3035: `_PKG_MGR = _STACK_DIR / "infra" / "default-pkg" / "_framework" / "_pkg-mgr" / "run"`
- Line 11252: `candidate = Path(repo_root) / "infra" / "default-pkg" / "_framework" / "_unit-mgr" / "run"`

The GUI already requires `set_env.sh` to be sourced (raises `RuntimeError` if `_GUI_DIR`
etc. are unset), so it has access to all `set_env.sh` exports. Both hardcoded paths are
replaced with `os.environ['_PKG_MGR']` / `os.environ['_UNIT_MGR']`.

### Scripts that KEEP `run`

- `_generate-inventory/run` — sibling `Makefile` calls `./run`
- `_git_root/run` — sibling `Makefile` calls `./run`
- `infra/<pkg>/_clean_all/run` — framework constructs path by convention
- `infra/<pkg>/_tg_scripts/…/run` — Terragrunt calls directly
- `scripts/wave-scripts/…/run` — Ansible hooks call directly

---

## Rename Table

| Tier | Current Path | New Name | Env var in `set_env.sh` |
|---|---|---|---|
| 1 | `_framework/_config-mgr/run` | `config-mgr` | `_CONFIG_MGR` |
| 1 | `_framework/_pkg-mgr/run` | `pkg-mgr` | `_PKG_MGR` |
| 1 | `_framework/_unit-mgr/run` | `unit-mgr` | `_UNIT_MGR` |
| 1 | `_framework/_ephemeral/run` | `ephemeral` | `_EPHEMERAL` |
| 1 | `_framework/_clean_all/run` | `clean-all` | `_CLEAN_ALL` |
| 1 | `_framework/_fw-repo-mgr/run` | `fw-repo-mgr` | `_FW_REPO_MGR` |
| 2 | `_human-only-scripts/purge-gcs-status/run` | `purge-gcs-status` | — (human-only) |
| 2 | `_human-only-scripts/setup-ephemeral-dirs/run` | `setup-ephemeral-dirs` | — (human-only) |
| 2 | `_human-only-scripts/debug/fix-git-index-bits/run` | `fix-git-index-bits` | — (human-only) |
| 3 | `_ai-only-scripts/upgrade-routeros/run` | `upgrade-routeros` | — (human/AI-only) |
| 4 | `tg-scripts/write-exit-status/run` | `write-exit-status` | `_WRITE_EXIT_STATUS` (already exists; path updated) |

No `run` shims. All callers updated to use env vars or new names.

---

## Open Questions

None — ready to proceed.

---

## Files to Create / Modify

### `_git_root/set_env.sh` — add env vars for all Tier 1 tools + update `_WRITE_EXIT_STATUS`

In `_set_env_export_vars()`, after the existing `_GENERATE_INVENTORY` and
`_WRITE_EXIT_STATUS` exports, add the six new exports and update the
`_WRITE_EXIT_STATUS` path:

```bash
# Before (lines 18-19):
export _GENERATE_INVENTORY="$_FRAMEWORK_DIR/_generate-inventory/run"
export _WRITE_EXIT_STATUS="$_UTILITIES_DIR/tg-scripts/write-exit-status/run"

# After:
export _GENERATE_INVENTORY="$_FRAMEWORK_DIR/_generate-inventory/run"   # kept: has Makefile
export _WRITE_EXIT_STATUS="$_UTILITIES_DIR/tg-scripts/write-exit-status/write-exit-status"
export _CONFIG_MGR="$_FRAMEWORK_DIR/_config-mgr/config-mgr"
export _PKG_MGR="$_FRAMEWORK_DIR/_pkg-mgr/pkg-mgr"
export _UNIT_MGR="$_FRAMEWORK_DIR/_unit-mgr/unit-mgr"
export _EPHEMERAL="$_FRAMEWORK_DIR/_ephemeral/ephemeral"
export _CLEAN_ALL="$_FRAMEWORK_DIR/_clean_all/clean-all"
export _FW_REPO_MGR="$_FRAMEWORK_DIR/_fw-repo-mgr/fw-repo-mgr"
```

---

### `_git_root/run` — update Python tool-path constants to use `ENV` dict

Lines 126–131 currently hardcode paths using `Path` arithmetic. Replace with env var
lookups (ENV is already populated by `_source_env()` at module load):

```python
# Before:
GENERATE_INVENTORY  = FRAMEWORK_PKG_DIR / '_framework/_generate-inventory/run'
NUKE_ALL            = FRAMEWORK_PKG_DIR / '_framework/_clean_all/run'
INIT_SH             = FRAMEWORK_PKG_DIR / '_framework/_utilities/bash/init.sh'
PKG_MGR             = FRAMEWORK_PKG_DIR / '_framework/_pkg-mgr/run'
_VALIDATE_CONFIG_PY = FRAMEWORK_PKG_DIR / '_framework/_utilities/python/validate-config.py'
_EPHEMERAL_RUN      = FRAMEWORK_PKG_DIR / '_framework/_ephemeral/run'

# After:
GENERATE_INVENTORY  = FRAMEWORK_PKG_DIR / '_framework/_generate-inventory/run'  # Makefile
NUKE_ALL            = Path(ENV['_CLEAN_ALL'])
INIT_SH             = FRAMEWORK_PKG_DIR / '_framework/_utilities/bash/init.sh'
PKG_MGR             = Path(ENV['_PKG_MGR'])
_VALIDATE_CONFIG_PY = FRAMEWORK_PKG_DIR / '_framework/_utilities/python/validate-config.py'
_EPHEMERAL_RUN      = Path(ENV['_EPHEMERAL'])
```

---

### `_fw-repo-mgr/run` — use env vars instead of hardcoded paths

Line 7 (direct ephemeral call):
```bash
# Before:
bash "$_FRAMEWORK_DIR/_ephemeral/run" || true
# After:
bash "$_EPHEMERAL" || true
```

Line 12 (pkg-mgr assignment):
```bash
# Before:
PKG_MGR="$_FRAMEWORK_DIR/_pkg-mgr/run"
# After:
PKG_MGR="$_PKG_MGR"
```

---

### `de3-gui-pkg/homelab_gui.py` — replace all `default-pkg` hardcodes with env vars

`default-pkg` was the original name for `_framework-pkg` and no longer exists. All four
occurrences must be replaced. `set_env.sh` already exports `_FRAMEWORK_PKG_DIR` (points
to `infra/_framework-pkg`) and the new `_PKG_MGR` / `_UNIT_MGR` vars.

**Line 1089** — framework config path:
```python
# Before:
framework = _STACK_DIR / "infra" / "default-pkg" / "_config" / "framework.yaml"
# After:
framework = Path(os.environ['_FRAMEWORK_PKG_DIR']) / "_config" / "framework.yaml"
```

**Line 1236** — waves ordering path:
```python
# Before:
waves_ordering_path = _STACK_DIR / "infra" / "default-pkg" / "_config" / "waves_ordering.yaml"
# After:
waves_ordering_path = Path(os.environ['_FRAMEWORK_PKG_DIR']) / "_config" / "waves_ordering.yaml"
```

**Line 3035** — module-level `_PKG_MGR` constant:
```python
# Before:
_PKG_MGR = _STACK_DIR / "infra" / "default-pkg" / "_framework" / "_pkg-mgr" / "run"
# After:
_PKG_MGR = Path(os.environ['_PKG_MGR'])
```

**Lines 11252-11253** — `_find_unit_mgr()` function:
```python
# Before:
    candidate = Path(repo_root) / "infra" / "default-pkg" / "_framework" / "_unit-mgr" / "run"
    return str(candidate) if candidate.exists() else None
# After:
    candidate = Path(os.environ.get('_UNIT_MGR', ''))
    return str(candidate) if candidate and candidate.exists() else None
```

---

### Rename all scripts (git mv commands)

Run these from the de3-runner repo root
(`/home/pyoung/git/de3-ext-packages/de3-runner/main`):

```bash
# Tier 1 — core framework tools
git mv infra/_framework-pkg/_framework/_config-mgr/run \
       infra/_framework-pkg/_framework/_config-mgr/config-mgr

git mv infra/_framework-pkg/_framework/_pkg-mgr/run \
       infra/_framework-pkg/_framework/_pkg-mgr/pkg-mgr

git mv infra/_framework-pkg/_framework/_unit-mgr/run \
       infra/_framework-pkg/_framework/_unit-mgr/unit-mgr

git mv infra/_framework-pkg/_framework/_ephemeral/run \
       infra/_framework-pkg/_framework/_ephemeral/ephemeral

git mv infra/_framework-pkg/_framework/_clean_all/run \
       infra/_framework-pkg/_framework/_clean_all/clean-all

git mv infra/_framework-pkg/_framework/_fw-repo-mgr/run \
       infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr

# Tier 2 — human-only scripts
git mv infra/_framework-pkg/_framework/_human-only-scripts/purge-gcs-status/run \
       infra/_framework-pkg/_framework/_human-only-scripts/purge-gcs-status/purge-gcs-status

git mv infra/_framework-pkg/_framework/_human-only-scripts/setup-ephemeral-dirs/run \
       infra/_framework-pkg/_framework/_human-only-scripts/setup-ephemeral-dirs/setup-ephemeral-dirs

git mv infra/_framework-pkg/_framework/_human-only-scripts/debug/fix-git-index-bits/run \
       infra/_framework-pkg/_framework/_human-only-scripts/debug/fix-git-index-bits/fix-git-index-bits

# Tier 3 — active ai-only scripts
git mv infra/_framework-pkg/_framework/_ai-only-scripts/upgrade-routeros/run \
       infra/_framework-pkg/_framework/_ai-only-scripts/upgrade-routeros/upgrade-routeros

# Tier 4 — tg-script
git mv infra/_framework-pkg/_framework/_utilities/tg-scripts/write-exit-status/run \
       infra/_framework-pkg/_framework/_utilities/tg-scripts/write-exit-status/write-exit-status
```

---

### `_framework/README.md` — update tool descriptions to reference named scripts

Replace any `./run` invocation examples in the table rows with the named script.
No structural change — this is a documentation accuracy fix only.

---

## Execution Order

All changes are in two repos:
- **de3-runner** (`_ext_packages/de3-runner/main`): framework source
- **de3-gui-pkg** (inside de3-runner at `infra/de3-gui-pkg`): GUI

1. In de3-runner: run all `git mv` commands (Tiers 1–4).
2. In de3-runner: update `_git_root/set_env.sh` — add new env var exports, update `_WRITE_EXIT_STATUS` path.
3. In de3-runner: update `_git_root/run` — replace `NUKE_ALL`, `PKG_MGR`, `_EPHEMERAL_RUN` constants with `Path(ENV[...])`.
4. In de3-runner: update `_fw-repo-mgr/fw-repo-mgr` — replace hardcoded ephemeral and pkg-mgr paths with env vars.
5. In de3-gui-pkg: update `homelab_gui.py` lines 3035 and 11252-11253.
6. Update `_framework/README.md` invocation examples.
7. Commit all de3-runner changes together (includes gui-pkg since it lives in that repo).

## Verification

```bash
# In de3-runner repo — confirm no stale /run references to renamed scripts
grep -rn "_pkg-mgr/run\|_clean_all/run\|_ephemeral/run\|_unit-mgr/run\|_fw-repo-mgr/run\|_config-mgr/run\|write-exit-status/run" \
  infra/_framework-pkg/_framework/ \
  infra/de3-gui-pkg/ \
  --include="*.py" --include="*.sh" --include="*.hcl"

# Confirm new env vars are present in set_env.sh
grep "_PKG_MGR\|_UNIT_MGR\|_CONFIG_MGR\|_EPHEMERAL\|_CLEAN_ALL\|_FW_REPO_MGR" \
  infra/_framework-pkg/_framework/_git_root/set_env.sh

# Confirm named scripts are executable
for s in config-mgr pkg-mgr unit-mgr ephemeral clean-all fw-repo-mgr; do
  ls -la infra/_framework-pkg/_framework/_${s%%-*}*/$s 2>/dev/null \
    || ls -la infra/_framework-pkg/_framework/_${s//-/_}/$s 2>/dev/null
done

# In consumer repo — confirm env vars resolve correctly
source set_env.sh && echo $_PKG_MGR && echo $_UNIT_MGR && echo $_EPHEMERAL

# Confirm Makefiles still work (these scripts keep `run`)
ls infra/_framework-pkg/_framework/_generate-inventory/run
ls infra/_framework-pkg/_framework/_git_root/run
```
