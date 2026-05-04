# Plan: Robust, Consistent Bootstrap Env Vars — _FRAMEWORK_PKG_DIR + _MAIN_PKG_DIR

## Objective

Invert the bootstrap anchor so that `_FRAMEWORK_PKG_DIR` and `_MAIN_PKG_DIR` are the
two stable, explicitly-named roots — not `_GIT_ROOT`. `_GIT_ROOT` becomes a derived alias
kept only for backward compat. Every tool that currently falls back to `git rev-parse` will
instead derive the repo root from `_FRAMEWORK_PKG_DIR` (always set in environment) or, for
Python modules called via `cd SCRIPT_DIR && exec python3`, from `Path(__file__).parents[N]`
— eliminating all `git rev-parse` fragility.

## Context

### Current bootstrap flow

```
set_env.sh
  _GIT_ROOT  ← dirname(BASH_SOURCE[0])   ← the one true anchor
  _INFRA_DIR  = $_GIT_ROOT/infra
  _FRAMEWORK_PKG_DIR = $_INFRA_DIR/_framework-pkg
  _FRAMEWORK_MAIN_PACKAGE_DIR = $_INFRA_DIR/$_FRAMEWORK_MAIN_PACKAGE
  (everything else derived from _GIT_ROOT)
```

`_GIT_ROOT` is the anchor, but tools that need it after a `cd` can't use `git rev-parse`
reliably (because the CWD is the framework clone, not the consumer repo). Fixes applied in
the previous session add `${_GIT_ROOT:-$(git rev-parse ...)}` defensively, but that still
means `git rev-parse` runs from the wrong directory if the env var is absent.

### Proposed flow

```
set_env.sh
  _FRAMEWORK_PKG_DIR  ← dirname(BASH_SOURCE[0]) + "/infra/_framework-pkg"
                         (BASH_SOURCE resolves to set_env.sh at consumer root)
  _GIT_ROOT           ← derived = dirname(dirname(_FRAMEWORK_PKG_DIR))   [compat alias]
  _INFRA_DIR          ← derived = dirname(_FRAMEWORK_PKG_DIR)             [compat alias]
  _MAIN_PKG_DIR       ← _INFRA_DIR/$_FRAMEWORK_MAIN_PACKAGE
  (all tool paths and dynamic dirs derived from _FRAMEWORK_PKG_DIR and _MAIN_PKG_DIR)
```

### What currently uses each var

| Var | Used by |
|-----|---------|
| `_GIT_ROOT` | `set_env.sh` (anchor), `wave-mgr` (Python bootstrap), `run` (consumer), `fw-repo-mgr` shim, maas-state-cache.sh, framework-utils.sh, all bash entry points |
| `_FRAMEWORK_PKG_DIR` | `set_env.sh`, `framework_config.py`, `config_mgr/packages.py`, `fw_repos_diagram_exporter/config.py`, `unit_mgr/main.py`, `fw-repo-mgr` shim, `validate-config.py` |
| `_FRAMEWORK_MAIN_PACKAGE_DIR` | `set_env.sh`, `root.hcl`, `framework_config.py`, `config_mgr/packages.py`, `fw_repos_diagram_exporter/config.py`, `unit_mgr/main.py`, `fw-repo-mgr` (shim + Python) |
| `_CONFIG_DIR` | `root.hcl` (only Terragrunt accessor) |

### What `_GIT_ROOT` is actually used for (after env is set)

Almost nothing that can't be expressed as `dirname(dirname(_FRAMEWORK_PKG_DIR))`:
- `_INFRA_DIR`, `_CONFIG_TMP_DIR`, `_DYNAMIC_DIR` — all `$_GIT_ROOT/...`
- `_fw_backend` path in `set_env.sh` — `$_GIT_ROOT/config/...`
- `wave-mgr`/`run` Python bootstrap: only needs it to find `set_env.sh` and `infra/`
- `framework-utils.sh`: uses it inside `_find_component_config` (after env is set, so `_GIT_ROOT` is already available)

### Python bootstrap opportunity

Tools that `cd "${SCRIPT_DIR}" && exec python3 -m <module>` can derive `_FRAMEWORK_PKG_DIR`
from `Path(__file__)` with no `git rev-parse` and no environment dependency:

```
config_mgr/main.py lives at:
  _FRAMEWORK_PKG_DIR/_framework/_config-mgr/config_mgr/main.py
                                                              ↑ __file__
  parents[0] = config_mgr/
  parents[1] = _config-mgr/
  parents[2] = _framework/
  parents[3] = _FRAMEWORK_PKG_DIR
```

Same logic applies to `unit_mgr/main.py` and `fw_repos_diagram_exporter/main.py`.

### Idempotency guard

Current: `[[ -n "${_GIT_ROOT:-}" && -n "${_UTILITIES_DIR:-}" ]]`
Proposed: `[[ -n "${_FRAMEWORK_PKG_DIR:-}" && -n "${_UTILITIES_DIR:-}" ]]`
(Since `_FRAMEWORK_PKG_DIR` is always set when env is initialized, and `_UTILITIES_DIR` is always derived from it.)

### fw-repo-mgr shim

The shim at line 675 of `fw-repo-mgr` generates a temporary `set_env.sh` replacement. It sets
`_FRAMEWORK_MAIN_PACKAGE_DIR` — will need to also set `_MAIN_PKG_DIR` (or change to `_MAIN_PKG_DIR`
depending on transition strategy).

## Open Questions

1. **Transition strategy for `_FRAMEWORK_MAIN_PACKAGE_DIR`**: Three options:
   - (a) Hard rename to `_MAIN_PKG_DIR` everywhere, remove old name (breaking for any external scripts)
   - (b) Export both — `_MAIN_PKG_DIR` (new canonical) and `_FRAMEWORK_MAIN_PACKAGE_DIR` (legacy alias, deprecated)
   - (c) Keep `_FRAMEWORK_MAIN_PACKAGE_DIR` as canonical, add `_MAIN_PKG_DIR` as shorter alias
   **Preference?**

2. **`_GIT_ROOT` fate**: Keep as an exported derived alias (for backward compat) or remove? The
   consumer `run` script uses it directly and would need updating if removed. If kept as alias,
   it stays available but is no longer the bootstrap anchor.

3. **Python `_repo_root()` fallback**: For Python modules invoked via `cd SCRIPT_DIR && exec python3`,
   should the fallback be:
   - (a) `Path(__file__).parents[3]` → derive `_GIT_ROOT` from that (no env, no git)
   - (b) `os.environ.get("_FRAMEWORK_PKG_DIR")` → derive `_GIT_ROOT` as `parent.parent`
   - (c) Both: check env first, then `Path(__file__)`, then `git rev-parse` last resort
   Option (c) is most robust. **Agree?**

4. **Consumer `run` script**: It uses `_GIT_ROOT = Path(subprocess.check_output(['git', 'rev-parse',
   ...]))` at the top. Should this also be updated to use `Path(__file__).parent` (since `run` is at
   the consumer repo root)? Or is `git rev-parse` acceptable there since `run` is always invoked
   from the consumer root?

5. **Scope of `_INFRA_DIR`**: Should it be kept as an exported var or dropped (derivable from
   `_FRAMEWORK_PKG_DIR.parent`)? It's used in `framework-utils.sh` `_find_component_config`.

## Files to Create / Modify

### `infra/_framework-pkg/_framework/_git_root/set_env.sh` — modify

Restructure `_set_env_export_vars()` into two clearly-commented blocks:

**Block 1 — Bootstrap anchors (set once, never re-derived)**:
```bash
# ── Bootstrap anchors ─────────────────────────────────────────────────────────
# _FRAMEWORK_PKG_DIR is always correct — set_env.sh sits at consumer repo root,
# so dirname(BASH_SOURCE[0]) is always the consumer root, and _framework-pkg
# is always at infra/_framework-pkg relative to it.
_BOOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export _FRAMEWORK_PKG_DIR="$_BOOT_ROOT/infra/_framework-pkg"

# _GIT_ROOT: legacy alias — do not use in new code; derive from _FRAMEWORK_PKG_DIR
export _GIT_ROOT="$_BOOT_ROOT"                   # _BOOT_ROOT == repo root by convention

export _INFRA_DIR="$_BOOT_ROOT/infra"
export _FRAMEWORK_DIR="$_FRAMEWORK_PKG_DIR/_framework"

# _MAIN_PKG_DIR: path to the deployment-specific main package.
# Reads _FRAMEWORK_MAIN_PACKAGE from config/_framework.yaml if not already set.
if [[ -z "${_FRAMEWORK_MAIN_PACKAGE:-}" && -n "${_FRAMEWORK_CONFIG_PKG:-}" ]]; then
    _FRAMEWORK_MAIN_PACKAGE="$_FRAMEWORK_CONFIG_PKG"
fi
if [[ -z "${_FRAMEWORK_MAIN_PACKAGE:-}" ]]; then
    export _FRAMEWORK_MAIN_PACKAGE
    _FRAMEWORK_MAIN_PACKAGE="$(python3 "$_FRAMEWORK_DIR/_utilities/python/read-set-env.py" config-pkg "$_GIT_ROOT")"
fi
export _MAIN_PKG_DIR=""
if [[ -n "${_FRAMEWORK_MAIN_PACKAGE:-}" ]]; then
    export _MAIN_PKG_DIR
    _MAIN_PKG_DIR="$(realpath "$_INFRA_DIR/$_FRAMEWORK_MAIN_PACKAGE" 2>/dev/null || echo "$_INFRA_DIR/$_FRAMEWORK_MAIN_PACKAGE")"
fi
# Legacy aliases — deprecated; will be removed in a future release
export _FRAMEWORK_MAIN_PACKAGE_DIR="$_MAIN_PKG_DIR"
export _FRAMEWORK_CONFIG_PKG="$_FRAMEWORK_MAIN_PACKAGE"
export _FRAMEWORK_CONFIG_PKG_DIR="$_MAIN_PKG_DIR"
```

**Block 2 — Derived vars (all expressed in terms of anchors)**:
Everything currently under `_set_env_export_vars` after `_FRAMEWORK_DIR` definition — tool paths,
`_UTILITIES_DIR`, `_CONFIG_TMP_DIR`, `_DYNAMIC_DIR`, `_GCS_BUCKET`, etc. These are already
expressed in terms of `$_FRAMEWORK_DIR` and `$_INFRA_DIR`, so no change to the expressions.
Only the idempotency guard changes:

```bash
# Change line 15 from:
[[ -n "${_GIT_ROOT:-}" && -n "${_UTILITIES_DIR:-}" ]] && return 0
# To:
[[ -n "${_FRAMEWORK_PKG_DIR:-}" && -n "${_UTILITIES_DIR:-}" ]] && return 0
```

### `infra/_framework-pkg/_framework/_config-mgr/config_mgr/main.py` — modify

Replace current `_repo_root()` (which checks `_GIT_ROOT`) with a three-tier fallback:

```python
def _repo_root() -> Path:
    # Tier 1: _FRAMEWORK_PKG_DIR is set by set_env.sh — most reliable.
    # Derive repo root as FRAMEWORK_PKG_DIR/../../  (infra/_framework-pkg → infra → repo)
    fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
    if fw_pkg:
        return Path(fw_pkg).parent.parent

    # Tier 2: Legacy _GIT_ROOT alias (set by same set_env.sh).
    if env_root := os.environ.get("_GIT_ROOT"):
        return Path(env_root)

    # Tier 3: Derive from __file__ — works when called via cd SCRIPT_DIR && exec python3.
    # config_mgr/main.py lives at _FRAMEWORK_PKG_DIR/_framework/_config-mgr/config_mgr/main.py
    # parents: [0]=config_mgr/, [1]=_config-mgr/, [2]=_framework/, [3]=_FRAMEWORK_PKG_DIR
    return Path(__file__).parents[3].parent.parent
```

Remove the now-redundant `import os` guard (it's already imported).

### `infra/_framework-pkg/_framework/_unit-mgr/unit_mgr/main.py` — modify

Same three-tier `_repo_root()` as `config_mgr/main.py`. Path depth is identical:
`unit_mgr/main.py` → `parents[3]` = `_FRAMEWORK_PKG_DIR`.

```python
def _repo_root() -> Path:
    fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
    if fw_pkg:
        return Path(fw_pkg).parent.parent
    if env_root := os.environ.get("_GIT_ROOT"):
        return Path(env_root)
    # unit_mgr/main.py: _FRAMEWORK_PKG_DIR/_framework/_unit-mgr/unit_mgr/main.py
    return Path(__file__).parents[3].parent.parent
```

### `infra/_framework-pkg/_framework/_fw_repos_diagram_exporter/fw_repos_diagram_exporter/config.py` — modify

Same pattern. File is at `_FRAMEWORK_PKG_DIR/_framework/_fw_repos_diagram_exporter/fw_repos_diagram_exporter/config.py`:
- `parents[3]` = `_FRAMEWORK_PKG_DIR`

Update `repo_root()` to the same three-tier pattern.

### `infra/_framework-pkg/_framework/_utilities/python/framework_config.py` — modify

`find_framework_config_dirs()` and `fw_cfg_path()` already prefer `_FRAMEWORK_PKG_DIR` and
`_FRAMEWORK_MAIN_PACKAGE_DIR`. Update to also accept `_MAIN_PKG_DIR`:

```python
config_pkg_dir = os.environ.get("_MAIN_PKG_DIR") or os.environ.get("_FRAMEWORK_MAIN_PACKAGE_DIR")
```

### `infra/_framework-pkg/_framework/_config-mgr/config_mgr/packages.py` — modify

Same: update `_fw_cfg_path()` to check `_MAIN_PKG_DIR` then `_FRAMEWORK_MAIN_PACKAGE_DIR`:
```python
config_pkg_dir = os.environ.get("_MAIN_PKG_DIR") or os.environ.get("_FRAMEWORK_MAIN_PACKAGE_DIR")
```

### `infra/_framework-pkg/_framework/_utilities/python/validate-config.py` — modify

Same as `framework_config.py` — update `_FRAMEWORK_MAIN_PACKAGE_DIR` references to check
`_MAIN_PKG_DIR` first.

### `infra/_framework-pkg/_framework/_wave-mgr/wave-mgr` — modify

Replace the `_GIT_ROOT` derivation with `_FRAMEWORK_PKG_DIR`-first:

```python
# Tier 1: _FRAMEWORK_PKG_DIR set by set_env.sh; derive repo root from it.
_fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
if _fw_pkg:
    _GIT_ROOT = Path(_fw_pkg).parent.parent
else:
    # Tier 2: legacy alias
    _env_gr = os.environ.get("_GIT_ROOT")
    if _env_gr:
        _GIT_ROOT = Path(_env_gr)
    else:
        # Tier 3: wave-mgr is always at consumer root, so __file__.parent is there.
        # wave-mgr IS the repo root file (no parent dirs to navigate).
        _GIT_ROOT = Path(os.environ.get('PWD', os.getcwd()))

sys.path.insert(0, str(_GIT_ROOT / 'infra' / '_framework-pkg' / '_framework' / '_utilities' / 'python'))
```

Also update `_source_env()` to use same priority:
```python
def _source_env() -> dict:
    fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
    if fw_pkg:
        git_root = str(Path(fw_pkg).parent.parent)
    else:
        git_root = os.environ.get("_GIT_ROOT") or subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel'], text=True
        ).strip()
    ...
```

### `infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr` — modify

Update the shim generator (line 675) to also export `_MAIN_PKG_DIR`:
```python
set_env_link.write_text(
    "#!/bin/bash\n"
    '_SHIM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'  # use BASH_SOURCE, not git
    f'export _FRAMEWORK_PKG_DIR="{caller_fw_pkg_dir}"\n'
    f'export _FRAMEWORK_MAIN_PACKAGE="{config_pkg}"\n'
    f'export _MAIN_PKG_DIR="$_SHIM_ROOT/infra/{config_pkg}"\n'
    f'export _FRAMEWORK_MAIN_PACKAGE_DIR="$_SHIM_ROOT/infra/{config_pkg}"\n'  # legacy
    f'export _FRAMEWORK_CONFIG_PKG="{config_pkg}"\n'
    f'export _FRAMEWORK_CONFIG_PKG_DIR="$_SHIM_ROOT/infra/{config_pkg}"\n'
    'export _GCS_BUCKET=""\n'
    'export _CONFIG_TMP_DIR="$_SHIM_ROOT/config/tmp"\n'
    'export _DYNAMIC_DIR="$_SHIM_ROOT/config/tmp/dynamic"\n'
)
```

Also update `_git_root()` in `fw-repo-mgr` to check `_FRAMEWORK_PKG_DIR` before `_GIT_ROOT`:
```python
def _git_root() -> str:
    fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
    if fw_pkg:
        return str(Path(fw_pkg).parent.parent)
    if os.environ.get("_GIT_ROOT"):
        return os.environ["_GIT_ROOT"]
    # Walk up from logical $PWD
    ...
```

### `infra/_framework-pkg/_framework/_git_root/root.hcl` — modify

Update the `_framework_main_package_dir` local to prefer `_MAIN_PKG_DIR`:
```hcl
_framework_main_package_dir = coalesce(get_env("_MAIN_PKG_DIR", ""), get_env("_FRAMEWORK_MAIN_PACKAGE_DIR", ""))
```

### Consumer repo `run` script (`run` at repo root) — modify (consumer-side change)

`run` line 42 uses `subprocess.check_output(['git', 'rev-parse', ...])`. Since `run` is a Python
script at the consumer repo root and is always invoked as `./run` (CWD = repo root), replace with:
```python
_GIT_ROOT = Path(__file__).parent.resolve()
```

This eliminates the only remaining `git rev-parse` call in the consumer bootstrap.

## Execution Order

1. **`set_env.sh`** — the anchor; change idempotency guard, add `_MAIN_PKG_DIR` export, add legacy aliases. This is safe to do first because nothing else changes yet — `_FRAMEWORK_MAIN_PACKAGE_DIR` is still exported.

2. **`framework_config.py`** — update to read `_MAIN_PKG_DIR || _FRAMEWORK_MAIN_PACKAGE_DIR`. Backward compat preserved.

3. **`config_mgr/packages.py`** — same dual-read pattern.

4. **`validate-config.py`** — same.

5. **`config_mgr/main.py`** — update `_repo_root()` to three-tier.

6. **`unit_mgr/main.py`** — update `_repo_root()` to three-tier.

7. **`fw_repos_diagram_exporter/config.py`** — update `repo_root()` to three-tier.

8. **`fw-repo-mgr`** — update `_git_root()` and shim generator.

9. **`wave-mgr`** — update `_GIT_ROOT` derivation and `_source_env()`.

10. **`root.hcl`** — update `_framework_main_package_dir` to prefer `_MAIN_PKG_DIR`.

11. **Consumer `run` script** — update `_GIT_ROOT` derivation (this is in the consumer repo, committed separately).

## Verification

After execution, verify:

```bash
# 1. Sourcing set_env.sh exports the new var
source set_env.sh
echo "_FRAMEWORK_PKG_DIR=$_FRAMEWORK_PKG_DIR"       # should be non-empty
echo "_MAIN_PKG_DIR=$_MAIN_PKG_DIR"                  # should be non-empty (if main pkg set)
echo "_GIT_ROOT=$_GIT_ROOT"                          # should still work (legacy)
echo "_FRAMEWORK_MAIN_PACKAGE_DIR=$_FRAMEWORK_MAIN_PACKAGE_DIR"  # legacy alias

# 2. config-mgr works when run from inside framework dir
cd infra/_framework-pkg/_framework/_config-mgr
config-mgr generate --output-mode verbose  # should scan consumer repo packages

# 3. unit-mgr identifies correct repo root
unit-mgr --help  # should not error

# 4. Terragrunt can apply a unit
cd infra/pwy-home-lab-pkg/_stack/<some-unit>
terragrunt plan  # should load _CONFIG_DIR correctly

# 5. wave-mgr lists waves
wave-mgr --list-waves  # should show all waves

# 6. Check idempotency guard works
source set_env.sh  # second source — should return immediately (idempotent)
```
