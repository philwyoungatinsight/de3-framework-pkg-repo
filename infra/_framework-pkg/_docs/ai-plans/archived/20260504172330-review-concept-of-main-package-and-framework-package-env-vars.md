# Plan: Robust, Consistent Bootstrap — _FRAMEWORK_PKG_DIR + _MAIN_PKG_DIR as Primary Anchors

## Objective

Make env-var bootstrap simple and deterministic across all framework tools:
- Two primary anchors: `_FRAMEWORK_PKG_DIR` (always set) and `_MAIN_PKG_DIR` (set if main package exists)
- Rule: if vars are already in the environment, use them; if not, set them once from `git rev-parse` + YAML
- Remove `_GIT_ROOT` as an exported var — it is redundant given `_FRAMEWORK_PKG_DIR`
- Hard-rename `_FRAMEWORK_MAIN_PACKAGE_DIR` → `_MAIN_PKG_DIR` everywhere, drop all legacy aliases
- No multi-tier fallback chains in tools — just one check: env var set? use it. Not set? compute it once

## Context

### Current bootstrap flow (fragile, anchored on _GIT_ROOT)

```
set_env.sh (BASH_SOURCE → consumer repo root = _GIT_ROOT)
  _GIT_ROOT         ← dirname(BASH_SOURCE[0])         ← primary anchor
  _INFRA_DIR        = _GIT_ROOT/infra
  _FRAMEWORK_PKG_DIR = _INFRA_DIR/_framework-pkg       ← derived
  _FRAMEWORK_MAIN_PACKAGE_DIR = _INFRA_DIR/$MAIN_PKG  ← derived
```

Tools that `cd SCRIPT_DIR && exec python3` then need to reconstruct `_GIT_ROOT` because
the CWD is wrong for `git rev-parse`. Recent defensive fixes added `${_GIT_ROOT:-$(git rev-parse)}`
everywhere, which is fragile and inconsistent.

### Proposed bootstrap flow (simple, anchored on _FRAMEWORK_PKG_DIR)

```
set_env.sh
  _FRAMEWORK_PKG_DIR ← dirname(BASH_SOURCE[0]) + "/infra/_framework-pkg"   ← primary anchor
  _INFRA_DIR         ← dirname(_FRAMEWORK_PKG_DIR)                           ← derived
  [local _repo_root] ← dirname(_INFRA_DIR)                                   ← internal only, NOT exported
  _MAIN_PKG_DIR      ← _INFRA_DIR/$_FRAMEWORK_MAIN_PACKAGE                  ← second anchor
  (all tool paths and dynamic dirs derived from _FRAMEWORK_PKG_DIR)
```

Bash tool wrappers that `cd SCRIPT_DIR` first set `_FRAMEWORK_PKG_DIR` from their own `BASH_SOURCE`
location if it isn't already set. Python tools then read `_FRAMEWORK_PKG_DIR` from env — no
`git rev-parse` anywhere in library code.

`_GIT_ROOT` remains a local internal variable in set_env.sh (for concise expression of
`_CONFIG_TMP_DIR = _GIT_ROOT/config/tmp`) but is **not exported**.

### Scope of changes

All changes are in one repo: `de3-framework-pkg-repo`. The changes propagate to all
consumer repos automatically via the `infra/_framework-pkg` symlink.

Consumer-specific files that also need updating (outside the symlink):
- All `run` scripts (9 repos): use `_GIT_ROOT` as a local Python var — rename to `_repo_root` internally
- `de3-pwy-home-lab-pkg-repo/infra/pwy-home-lab-pkg/_setup/git-auth-check.py`: uses `_FRAMEWORK_CONFIG_PKG_DIR` → update to `_MAIN_PKG_DIR`

### Env vars: before vs after

| Before | After | Notes |
|--------|-------|-------|
| `_GIT_ROOT` (exported) | removed from exports | local `_repo_root` in set_env.sh only |
| `_FRAMEWORK_PKG_DIR` (exported) | `_FRAMEWORK_PKG_DIR` (primary anchor) | no change to name |
| `_FRAMEWORK_MAIN_PACKAGE_DIR` (exported) | `_MAIN_PKG_DIR` (exported) | renamed |
| `_FRAMEWORK_CONFIG_PKG_DIR` (exported legacy alias) | removed | no more aliases |
| `_FRAMEWORK_CONFIG_PKG` (exported legacy alias) | removed | `_FRAMEWORK_MAIN_PACKAGE` kept |
| `_INFRA_DIR` (exported) | `_INFRA_DIR` (exported) | now derived from `_FRAMEWORK_PKG_DIR` |

### Idempotency guard change

```bash
# Before:
[[ -n "${_GIT_ROOT:-}" && -n "${_UTILITIES_DIR:-}" ]] && return 0
# After:
[[ -n "${_FRAMEWORK_PKG_DIR:-}" && -n "${_UTILITIES_DIR:-}" ]] && return 0
```

### How bash wrappers set _FRAMEWORK_PKG_DIR before cd

Each bash entry-point (`config-mgr`, `unit-mgr`, `fw-repos-diagram-exporter`) currently does:
```bash
. "$(git rev-parse --show-toplevel)/set_env.sh"
cd "${SCRIPT_DIR}" && exec python3 -m <module> "$@"
```

After this plan, the pattern becomes:
```bash
# Set _FRAMEWORK_PKG_DIR from this script's location if not already in env.
# e.g. config-mgr lives at _FRAMEWORK_PKG_DIR/_framework/_config-mgr/config-mgr
#   so SCRIPT_DIR/../.. = _FRAMEWORK_PKG_DIR
export _FRAMEWORK_PKG_DIR="${_FRAMEWORK_PKG_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
. "$_FRAMEWORK_PKG_DIR/../../set_env.sh"    # idempotent; returns early if already sourced
cd "${SCRIPT_DIR}" && exec python3 -m <module> "$@"
```

Python then reads `_FRAMEWORK_PKG_DIR` from `os.environ` — always present, no fallback needed:
```python
def _repo_root() -> Path:
    fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
    if fw_pkg:
        return Path(fw_pkg).parent.parent
    # Only reached if invoked completely outside the framework (dev one-off).
    return Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    ).stdout.strip())
```

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/_framework-pkg/_framework/_git_root/set_env.sh` — modify

Full restructure of `_set_env_export_vars()`:

```bash
_set_env_export_vars() {
    # ── Primary anchors ─────────────────────────────────────────────────────
    # _FRAMEWORK_PKG_DIR is derived from BASH_SOURCE[0] (path of set_env.sh
    # itself, which is always a symlink at the consumer repo root). This avoids
    # git rev-parse and works correctly from any subdirectory or symlinked context.
    if [[ -z "${_FRAMEWORK_PKG_DIR:-}" ]]; then
        local _boot_root
        _boot_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [[ -z "$_boot_root" ]]; then
            echo "FATAL: could not determine repo root from BASH_SOURCE." >&2; return 1
        fi
        export _FRAMEWORK_PKG_DIR="$_boot_root/infra/_framework-pkg"
    fi

    # Internal repo root — NOT exported. Use _FRAMEWORK_PKG_DIR in all new code.
    local _repo_root
    _repo_root="$(dirname "$(dirname "$_FRAMEWORK_PKG_DIR")")"

    export _INFRA_DIR="$(dirname "$_FRAMEWORK_PKG_DIR")"
    export _FRAMEWORK_DIR="$_FRAMEWORK_PKG_DIR/_framework"
    export _UTILITIES_DIR="$_FRAMEWORK_DIR/_utilities"
    # ... all tool path exports unchanged (use $_FRAMEWORK_DIR) ...

    # ── Main package ────────────────────────────────────────────────────────
    if [[ -z "${_FRAMEWORK_MAIN_PACKAGE:-}" ]]; then
        export _FRAMEWORK_MAIN_PACKAGE
        _FRAMEWORK_MAIN_PACKAGE="$(python3 "$_FRAMEWORK_DIR/_utilities/python/read-set-env.py" config-pkg "$_repo_root")"
    fi
    export _MAIN_PKG_DIR=""
    if [[ -n "${_FRAMEWORK_MAIN_PACKAGE:-}" ]]; then
        export _MAIN_PKG_DIR
        _MAIN_PKG_DIR="$(realpath "$_INFRA_DIR/$_FRAMEWORK_MAIN_PACKAGE" 2>/dev/null \
                         || echo "$_INFRA_DIR/$_FRAMEWORK_MAIN_PACKAGE")"
    fi

    # ── Dynamic dirs (all relative to _repo_root) ───────────────────────────
    export _CONFIG_TMP_DIR="$_repo_root/config/tmp"
    export _DYNAMIC_DIR="$_CONFIG_TMP_DIR/dynamic"
    export _RAMDISK_DIR="$_DYNAMIC_DIR/ramdisk"
    export _WAVE_LOGS_DIR="$_DYNAMIC_DIR/run-wave-logs"
    export _GUI_DIR="$_DYNAMIC_DIR/gui"
    export _CONFIG_DIR="$_DYNAMIC_DIR/config"

    # ── GCS backend (3-tier lookup using _repo_root internally) ─────────────
    local _fw_backend
    if [[ -f "$_repo_root/config/framework_backend.yaml" ]]; then
        _fw_backend="$_repo_root/config/framework_backend.yaml"
    elif [[ -n "${_MAIN_PKG_DIR:-}" && \
            -f "$_MAIN_PKG_DIR/_config/_framework_settings/framework_backend.yaml" ]]; then
        _fw_backend="$_MAIN_PKG_DIR/_config/_framework_settings/framework_backend.yaml"
    else
        _fw_backend="$_FRAMEWORK_PKG_DIR/_config/_framework_settings/framework_backend.yaml"
    fi
    export _GCS_BUCKET
    _GCS_BUCKET="$(python3 "$_FRAMEWORK_DIR/_utilities/python/read-set-env.py" gcs-bucket "$_fw_backend")"
}
```

Change idempotency guard (line 15):
```bash
[[ -n "${_FRAMEWORK_PKG_DIR:-}" && -n "${_UTILITIES_DIR:-}" ]] && return 0
```

Remove the legacy alias exports entirely:
```bash
# DELETE these lines:
export _FRAMEWORK_CONFIG_PKG="$_FRAMEWORK_MAIN_PACKAGE"
export _FRAMEWORK_CONFIG_PKG_DIR="$_FRAMEWORK_MAIN_PACKAGE_DIR"
# Also delete the _FRAMEWORK_CONFIG_PKG migration block (lines 72-73)
```

### `infra/_framework-pkg/_framework/_config-mgr/config-mgr` — modify (bash entry)

Replace `git rev-parse` with `_FRAMEWORK_PKG_DIR`-first sourcing:

```bash
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# _config-mgr/ is one level below _framework/, which is one below _FRAMEWORK_PKG_DIR
export _FRAMEWORK_PKG_DIR="${_FRAMEWORK_PKG_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
. "$_FRAMEWORK_PKG_DIR/../../set_env.sh"
. "$_UTILITIES_DIR/bash/init.sh"
export PYTHON_VERSION='python3.12'
_activate_python_locally "$SCRIPT_DIR"
cd "${SCRIPT_DIR}" && exec python3 -m config_mgr.main "$@"
```

### `infra/_framework-pkg/_framework/_unit-mgr/unit-mgr` — modify (bash entry)

Same pattern. `unit-mgr` is at `_FRAMEWORK_PKG_DIR/_framework/_unit-mgr/unit-mgr`:

```bash
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export _FRAMEWORK_PKG_DIR="${_FRAMEWORK_PKG_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
. "$_FRAMEWORK_PKG_DIR/../../set_env.sh"
. "$_UTILITIES_DIR/bash/init.sh"
export PYTHON_VERSION='python3.12'
setup_python() { _activate_python_locally "$SCRIPT_DIR"; }
setup_python
cd "${SCRIPT_DIR}" && exec python3 -m unit_mgr.main "$@"
```

### `infra/_framework-pkg/_framework/_fw_repos_diagram_exporter/fw-repos-diagram-exporter` — modify (bash entry)

Same pattern:
```bash
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export _FRAMEWORK_PKG_DIR="${_FRAMEWORK_PKG_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
. "$_FRAMEWORK_PKG_DIR/../../set_env.sh"
. "$_UTILITIES_DIR/bash/init.sh"
export PYTHON_VERSION='python3.12'
_activate_python_locally "$SCRIPT_DIR"
cd "${SCRIPT_DIR}" && exec python3 -m fw_repos_diagram_exporter.main "$@"
```

### `infra/_framework-pkg/_framework/_pkg-mgr/pkg-mgr` — modify (bash entry)

```bash
# Replace lines 3-5:
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export _FRAMEWORK_PKG_DIR="${_FRAMEWORK_PKG_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
source "$_FRAMEWORK_PKG_DIR/../../set_env.sh"
GIT_ROOT="$(dirname "$(dirname "$_FRAMEWORK_PKG_DIR")")"   # local only, pkg-mgr uses this var
```

Note: `pkg-mgr` is at `_FRAMEWORK_PKG_DIR/_framework/_pkg-mgr/pkg-mgr` — so `$SCRIPT_DIR/..` = `_framework/`, and `$SCRIPT_DIR/../..` = `_FRAMEWORK_PKG_DIR`. Actually `SCRIPT_DIR` is the `_pkg-mgr/` directory. So `$SCRIPT_DIR/..` = `_framework/` and `$SCRIPT_DIR/../..` = `_FRAMEWORK_PKG_DIR`. ✓

Also replace line 5 (`GIT_ROOT="$(git rev-parse --show-toplevel)"`):
```bash
GIT_ROOT="$(dirname "$(dirname "$_FRAMEWORK_PKG_DIR")")"
```

### `infra/_framework-pkg/_framework/_generate-inventory/run` — modify (bash entry)

```bash
# Replace the git rev-parse line:
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export _FRAMEWORK_PKG_DIR="${_FRAMEWORK_PKG_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
. "$_FRAMEWORK_PKG_DIR/../../set_env.sh"
```

(This script is at `_FRAMEWORK_PKG_DIR/_framework/_generate-inventory/run`)

### `infra/_framework-pkg/_framework/_ramdisk-mgr/ramdisk-mgr` — modify

Replace both `GIT_ROOT="$(git rev-parse --show-toplevel)"` occurrences (lines 66, 132) with:
```bash
GIT_ROOT="$(dirname "$(dirname "$_FRAMEWORK_PKG_DIR")")"
```
(ramdisk-mgr doesn't source set_env.sh before calling git rev-parse — it does so after.
Since `_FRAMEWORK_PKG_DIR` must be set by the time ramdisk-mgr runs, this is safe.)

Also update `source "$GIT_ROOT/set_env.sh"` → `source "$_FRAMEWORK_PKG_DIR/../../set_env.sh"`.

### `infra/_framework-pkg/_framework/_utilities/bash/framework-utils.sh` — modify

Line 22: source set_env.sh from `_FRAMEWORK_PKG_DIR`:
```bash
. "${_FRAMEWORK_PKG_DIR:?_FRAMEWORK_PKG_DIR must be set}/../../set_env.sh"
```
(uses `:?` to fail loudly if not set — no silent fallback to git rev-parse)

Line 81 in `_find_component_config`:
```bash
git_root="$(dirname "$(dirname "$_FRAMEWORK_PKG_DIR")")"
```

### `infra/_framework-pkg/_framework/_config-mgr/config_mgr/main.py` — modify

Simplify `_repo_root()` to two cases:
```python
def _repo_root() -> Path:
    fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
    if fw_pkg:
        return Path(fw_pkg).parent.parent
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(result.stdout.strip())
```

Remove the now-stale comment about `_GIT_ROOT`.

### `infra/_framework-pkg/_framework/_unit-mgr/unit_mgr/main.py` — modify

Same simplified `_repo_root()` as `config_mgr/main.py`.

### `infra/_framework-pkg/_framework/_fw_repos_diagram_exporter/fw_repos_diagram_exporter/config.py` — modify

Same simplified `repo_root()`. Also update `_FRAMEWORK_MAIN_PACKAGE_DIR` reference:
```python
config_pkg_dir = os.environ.get("_MAIN_PKG_DIR")
```

### `infra/_framework-pkg/_framework/_utilities/python/framework_config.py` — modify

Update both `_FRAMEWORK_MAIN_PACKAGE_DIR` references to `_MAIN_PKG_DIR`:
```python
config_pkg_dir = os.environ.get("_MAIN_PKG_DIR")
```
(lines 37 and 71)

### `infra/_framework-pkg/_framework/_config-mgr/config_mgr/packages.py` — modify

```python
config_pkg_dir = os.environ.get("_MAIN_PKG_DIR")
```

### `infra/_framework-pkg/_framework/_unit-mgr/unit_mgr/main.py` — modify (additional)

Line 80:
```python
pkg_dir = os.environ.get("_FRAMEWORK_PKG_DIR") or str(repo_root / "infra" / "_framework-pkg")
```
(this line already uses `_FRAMEWORK_PKG_DIR` — no change needed)

### `infra/_framework-pkg/_framework/_utilities/python/validate-config.py` — modify

Update `_FRAMEWORK_MAIN_PACKAGE_DIR` reference (line 150):
```python
config_pkg_dir = os.environ.get("_MAIN_PKG_DIR")
```

### `infra/_framework-pkg/_framework/_wave-mgr/wave-mgr` — modify

Replace the `_GIT_ROOT` derivation (lines 85-86) with `_FRAMEWORK_PKG_DIR`-first:
```python
_fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
if _fw_pkg:
    _GIT_ROOT = Path(_fw_pkg).parent.parent
else:
    _GIT_ROOT = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip())
sys.path.insert(0, str(_GIT_ROOT / "infra" / "_framework-pkg" / "_framework" / "_utilities" / "python"))
```

Replace `_source_env()` lines 96-98:
```python
def _source_env() -> dict:
    fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
    if fw_pkg:
        git_root = str(Path(fw_pkg).parent.parent)
    else:
        git_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    ...
```

(wave-mgr is a Python entry-point script, always run from consumer repo root — git rev-parse as
fallback is correct here since it runs before any `cd`)

### `infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr` — modify

Update `_git_root()` function (lines 30-46) to check `_FRAMEWORK_PKG_DIR` first:
```python
def _git_root() -> str:
    fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
    if fw_pkg:
        return str(Path(fw_pkg).parent.parent)
    # Walk up from logical $PWD (handles symlinked dirs correctly)
    pwd = pathlib.Path(os.environ.get("PWD") or os.getcwd())
    p = pwd
    while True:
        if (p / ".git").exists():
            return str(p)
        parent = p.parent
        if parent == p:
            break
        p = parent
    sys.exit("FATAL: not inside a git repository.")
```

Update the shim generator (line 675) to use `_MAIN_PKG_DIR` and remove legacy aliases:
```python
set_env_link.write_text(
    "#!/bin/bash\n"
    '_SHIM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
    f'export _FRAMEWORK_PKG_DIR="{caller_fw_pkg_dir}"\n'
    f'export _FRAMEWORK_MAIN_PACKAGE="{config_pkg}"\n'
    f'export _MAIN_PKG_DIR="$_SHIM_ROOT/infra/{config_pkg}"\n'
    'export _GCS_BUCKET=""\n'
    'export _CONFIG_TMP_DIR="$_SHIM_ROOT/config/tmp"\n'
    'export _DYNAMIC_DIR="$_SHIM_ROOT/config/tmp/dynamic"\n'
)
```

### `infra/_framework-pkg/_framework/_git_root/root.hcl` — modify

Update line 58:
```hcl
_framework_main_package_dir = get_env("_MAIN_PKG_DIR", "")
```

### `infra/_framework-pkg/_framework/_utilities/bash/maas-state-cache.sh` — modify

Update to derive git root from `_FRAMEWORK_PKG_DIR`:
```bash
_maas_state_git_root() {
    if [[ -n "${_FRAMEWORK_PKG_DIR:-}" ]]; then
        dirname "$(dirname "$_FRAMEWORK_PKG_DIR")"
    else
        git rev-parse --show-toplevel
    fi
}
```

### Consumer repos — `run` script in each repo — modify (9 files)

Each `run` script at the repo root uses `_GIT_ROOT` as a local Python variable. Since `run`
is always invoked as `./run` from the repo root, replace line 42 with:
```python
_GIT_ROOT = Path(__file__).parent.resolve()
```
This is cleaner than `git rev-parse` and avoids the subprocess entirely.

Repos to update:
- `de3-pwy-home-lab-pkg-repo/run`
- `de3-framework-pkg-repo/main/run`
- `de3-aws-pkg-repo/main/run`
- `de3-azure-pkg-repo/main/run`
- `de3-gcp-pkg-repo/main/run` (if it exists)
- `de3-maas-pkg-repo/main/run` (if it exists)
- `de3-proxmox-pkg-repo/main/run` (if it exists)
- `de3-image-maker-pkg-repo/main/run` (if it exists)
- `de3-mesh-central-pkg-repo/main/run` (if it exists)

Check which ones exist before editing.

### `de3-pwy-home-lab-pkg-repo/infra/pwy-home-lab-pkg/_setup/git-auth-check.py` — modify

Line 27: update `_FRAMEWORK_CONFIG_PKG_DIR` → `_MAIN_PKG_DIR`:
```python
fw_cfg_pkg = os.environ.get("_MAIN_PKG_DIR", "")
```

## Execution Order

1. **`set_env.sh`** — central change; all other scripts depend on the new var names being exported
2. **`framework_config.py`** and **`config_mgr/packages.py`** — update `_MAIN_PKG_DIR` env reads
3. **`validate-config.py`** — update `_MAIN_PKG_DIR`
4. **`config_mgr/main.py`**, **`unit_mgr/main.py`**, **`fw_repos_diagram_exporter/config.py`** — simplify `_repo_root()`
5. **Bash entry points**: `config-mgr`, `unit-mgr`, `fw-repos-diagram-exporter`, `pkg-mgr`, `generate-inventory/run` — switch to `_FRAMEWORK_PKG_DIR`-first sourcing
6. **`ramdisk-mgr`**, **`framework-utils.sh`**, **`maas-state-cache.sh`** — replace git rev-parse with `_FRAMEWORK_PKG_DIR` derivation
7. **`wave-mgr`** and **`fw-repo-mgr`** — update Python bootstrap
8. **`root.hcl`** — update `_MAIN_PKG_DIR` env read
9. **Consumer `run` scripts** — `Path(__file__).parent.resolve()` for all repos that have one
10. **`git-auth-check.py`** — update `_MAIN_PKG_DIR` ref

## Verification

```bash
# 1. Source set_env.sh — check new vars are set, old ones gone
source set_env.sh
echo "_FRAMEWORK_PKG_DIR=$_FRAMEWORK_PKG_DIR"   # non-empty
echo "_MAIN_PKG_DIR=$_MAIN_PKG_DIR"             # non-empty (if main pkg configured)
echo "_INFRA_DIR=$_INFRA_DIR"                   # non-empty
printenv | grep _GIT_ROOT                        # should print nothing
printenv | grep _FRAMEWORK_CONFIG_PKG            # should print nothing
printenv | grep _FRAMEWORK_MAIN_PACKAGE_DIR      # should print nothing

# 2. config-mgr generates correctly (proves _repo_root() works after cd)
config-mgr generate --output-mode verbose        # should list consumer repo packages

# 3. unit-mgr works
unit-mgr --help

# 4. Terragrunt reads _MAIN_PKG_DIR correctly
cd infra/pwy-home-lab-pkg/_stack/<any-unit>
terragrunt plan 2>&1 | grep -v "error"

# 5. wave-mgr lists waves
wave-mgr --list-waves

# 6. Idempotency: second source returns immediately
source set_env.sh && echo "idempotent OK"

# 7. Verify no scripts still reference _GIT_ROOT or _FRAMEWORK_MAIN_PACKAGE_DIR
grep -r '_GIT_ROOT\|_FRAMEWORK_MAIN_PACKAGE_DIR\|_FRAMEWORK_CONFIG_PKG_DIR' \
  infra/_framework-pkg/_framework/ --include='*.sh' --include='*.py' --include='*.hcl'
# Should return no hits
```
