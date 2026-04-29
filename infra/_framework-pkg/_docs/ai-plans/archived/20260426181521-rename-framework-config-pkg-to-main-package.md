# Plan: Rename `_FRAMEWORK_CONFIG_PKG` → `_FRAMEWORK_MAIN_PACKAGE`

## Objective

Rename the two env vars that identify the deployment's "main package" from
`_FRAMEWORK_CONFIG_PKG` / `_FRAMEWORK_CONFIG_PKG_DIR` to
`_FRAMEWORK_MAIN_PACKAGE` / `_FRAMEWORK_MAIN_PACKAGE_DIR`.

`_FRAMEWORK_MAIN_PACKAGE_DIR` will be realpath-resolved so that tools working
across symlinks always get a canonical absolute path. The old names will be
re-exported as aliases in `set_env.sh` for one release cycle to avoid breaking
any external scripts or CI that set `_FRAMEWORK_CONFIG_PKG` manually.

## Context

### Current state

`set_env.sh` (lines 59–71) reads `config/_framework.yaml` → `_framework.main_package`
via `read-set-env.py config-pkg`, exports:
- `_FRAMEWORK_CONFIG_PKG`     — package name, e.g. `pwy-home-lab-pkg`
- `_FRAMEWORK_CONFIG_PKG_DIR` — string concat `$_INFRA_DIR/$_FRAMEWORK_CONFIG_PKG`
  (NOT realpath-resolved; symlinks in the path are preserved)

### Files that reference the old names (live code only)

| File | Old var | How used |
|------|---------|----------|
| `set_env.sh` L62–85 | both | declares and exports them; uses `_DIR` for GCS backend lookup |
| `root.hcl` L58,62–63 | `_FRAMEWORK_CONFIG_PKG_DIR` | 3-tier framework_backend lookup |
| `fw-repo-mgr` L16–24,39,367–370,450,579–585 | both | 3-tier settings lookup; written into generated shim `set_env.sh` |
| `pkg-mgr` L21–23 | `_FRAMEWORK_CONFIG_PKG_DIR` | 3-tier settings lookup |
| `config-mgr/packages.py` L14,19 | `_FRAMEWORK_CONFIG_PKG_DIR` | `_fw_cfg_path` helper |
| `framework_config.py` L25,37,62,71 | `_FRAMEWORK_CONFIG_PKG_DIR` | `find_framework_config_dirs` / `fw_cfg_path` |
| `fw_repos_diagram_exporter/config.py` L15 | `_FRAMEWORK_CONFIG_PKG_DIR` | `_fw_cfg_path` helper |

### Files that do NOT need changes

- `read-set-env.py` — subcommand name `config-pkg` is an internal detail, not a public env var. Leave unchanged.
- `config/_framework.yaml` YAML key `main_package` — already renamed from `config_package`.
- Archived ai-plans, version_history.md — historical records; do not change.
- `config-overview.md`, `config-files.md` — update docs to use new names.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/_framework-pkg/_framework/_git_root/set_env.sh` — modify

Replace the config-package block (lines 59–71). New logic:
1. Accept pre-existing `_FRAMEWORK_MAIN_PACKAGE` (new) OR `_FRAMEWORK_CONFIG_PKG` (old alias) as override.
2. Fall through to `read-set-env.py config-pkg` if neither is set.
3. Export `_FRAMEWORK_MAIN_PACKAGE` and `_FRAMEWORK_MAIN_PACKAGE_DIR` (realpath-resolved).
4. Re-export old names as aliases pointing to the new vars.

```bash
    # --- Main package resolution ---
    # config/_framework.yaml declares which package is the "main package" — the deployment-
    # specific package that overrides framework defaults (e.g. pwy-home-lab-pkg).
    # A pre-existing _FRAMEWORK_MAIN_PACKAGE env var wins (for CI or per-dev overrides).
    # _FRAMEWORK_CONFIG_PKG is accepted as a legacy alias for one release cycle.
    if [[ -z "${_FRAMEWORK_MAIN_PACKAGE:-}" && -n "${_FRAMEWORK_CONFIG_PKG:-}" ]]; then
        _FRAMEWORK_MAIN_PACKAGE="$_FRAMEWORK_CONFIG_PKG"
    fi
    if [[ -z "${_FRAMEWORK_MAIN_PACKAGE:-}" ]]; then
        export _FRAMEWORK_MAIN_PACKAGE
        _FRAMEWORK_MAIN_PACKAGE="$(python3 "$_FRAMEWORK_DIR/_utilities/python/read-set-env.py" config-pkg "$_GIT_ROOT")"
    fi
    export _FRAMEWORK_MAIN_PACKAGE_DIR=""
    if [[ -n "${_FRAMEWORK_MAIN_PACKAGE:-}" ]]; then
        export _FRAMEWORK_MAIN_PACKAGE_DIR
        _FRAMEWORK_MAIN_PACKAGE_DIR="$(realpath "$_INFRA_DIR/$_FRAMEWORK_MAIN_PACKAGE" 2>/dev/null || echo "$_INFRA_DIR/$_FRAMEWORK_MAIN_PACKAGE")"
    fi
    # Legacy aliases — deprecated; remove in next major release
    export _FRAMEWORK_CONFIG_PKG="$_FRAMEWORK_MAIN_PACKAGE"
    export _FRAMEWORK_CONFIG_PKG_DIR="$_FRAMEWORK_MAIN_PACKAGE_DIR"
```

Also update the GCS backend comment block (lines 76–85) to use new var names in the
prose comments; the actual bash code already uses `_FRAMEWORK_CONFIG_PKG_DIR` which will
be kept as an alias, so the bash logic still works unchanged. Optionally update to use
`_FRAMEWORK_MAIN_PACKAGE_DIR` directly.

### `infra/_framework-pkg/_framework/_git_root/root.hcl` — modify

Line 58: `_framework_config_pkg_dir = get_env("_FRAMEWORK_CONFIG_PKG_DIR", "")`
→ `_framework_main_package_dir = get_env("_FRAMEWORK_MAIN_PACKAGE_DIR", get_env("_FRAMEWORK_CONFIG_PKG_DIR", ""))`

Lines 62–63: update HCL local name `_framework_config_pkg_dir` → `_framework_main_package_dir`
wherever it is referenced in this file.

### `infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr` — modify

All occurrences of `_FRAMEWORK_CONFIG_PKG_DIR` → `_FRAMEWORK_MAIN_PACKAGE_DIR`
All occurrences of `_FRAMEWORK_CONFIG_PKG` (non-`_DIR`) → `_FRAMEWORK_MAIN_PACKAGE`

In the generated shim `set_env.sh` snippet (lines ~579–580):
```bash
export _FRAMEWORK_MAIN_PACKAGE="$config_pkg"
export _FRAMEWORK_MAIN_PACKAGE_DIR="\$_SHIM_ROOT/infra/$config_pkg"
# Legacy aliases
export _FRAMEWORK_CONFIG_PKG="$config_pkg"
export _FRAMEWORK_CONFIG_PKG_DIR="\$_SHIM_ROOT/infra/$config_pkg"
```

Also update comment on line ~585:
`(export _FRAMEWORK_MAIN_PACKAGE="$config_pkg"; cd "$repo_dir"; "$PKG_MGR" --sync)`

And the usage note on line ~689:
`config/_framework.yaml           (sets _FRAMEWORK_MAIN_PACKAGE)`

### `infra/_framework-pkg/_framework/_pkg-mgr/pkg-mgr` — modify

Lines 21–23: `_FRAMEWORK_CONFIG_PKG_DIR` → `_FRAMEWORK_MAIN_PACKAGE_DIR` (all 3 occurrences in `_fw_cfg` function).

### `infra/_framework-pkg/_framework/_config-mgr/config_mgr/packages.py` — modify

Line 14 (comment): update to `_FRAMEWORK_MAIN_PACKAGE/_config/overrides/`
Line 19: `os.environ.get("_FRAMEWORK_CONFIG_PKG_DIR")` → `os.environ.get("_FRAMEWORK_MAIN_PACKAGE_DIR") or os.environ.get("_FRAMEWORK_CONFIG_PKG_DIR")`

### `infra/_framework-pkg/_framework/_utilities/python/framework_config.py` — modify

Line 25 (comment): update to `_FRAMEWORK_MAIN_PACKAGE`
Line 37: `os.environ.get("_FRAMEWORK_CONFIG_PKG_DIR")` → `os.environ.get("_FRAMEWORK_MAIN_PACKAGE_DIR") or os.environ.get("_FRAMEWORK_CONFIG_PKG_DIR")`
Line 62 (comment): update to `$_FRAMEWORK_MAIN_PACKAGE_DIR`
Line 71: same as line 37

### `infra/_framework-pkg/_framework/_fw_repos_diagram_exporter/fw_repos_diagram_exporter/config.py` — modify

Line 15: `os.environ.get("_FRAMEWORK_CONFIG_PKG_DIR")` → `os.environ.get("_FRAMEWORK_MAIN_PACKAGE_DIR") or os.environ.get("_FRAMEWORK_CONFIG_PKG_DIR")`

### `infra/_framework-pkg/_docs/config-overview.md` — modify

Lines 58–59: replace `_FRAMEWORK_CONFIG_PKG` / `_FRAMEWORK_CONFIG_PKG_DIR` with
`_FRAMEWORK_MAIN_PACKAGE` / `_FRAMEWORK_MAIN_PACKAGE_DIR` (note old names are aliases).

### `infra/_framework-pkg/_docs/framework/config-files.md` — modify

Lines 240–264: replace all `_FRAMEWORK_CONFIG_PKG` / `_FRAMEWORK_CONFIG_PKG_DIR`
references with the new names; note they are realpath-resolved.

### `infra/_framework-pkg/_config/_framework-pkg.yaml` — modify

Bump version: `1.19.0` → `1.20.0`

### `infra/_framework-pkg/_config/version_history.md` — modify

Prepend entry:
```markdown
## 1.20.0  (2026-04-26, git: <sha>)
- Rename _FRAMEWORK_CONFIG_PKG → _FRAMEWORK_MAIN_PACKAGE; _FRAMEWORK_CONFIG_PKG_DIR → _FRAMEWORK_MAIN_PACKAGE_DIR (realpath-resolved)
- Old names re-exported as aliases in set_env.sh for backward compatibility
- Python tools fall back to old env var name if new one is unset
- Update all live code: root.hcl, fw-repo-mgr, pkg-mgr, packages.py, framework_config.py, config.py (diagram exporter)
```

## Execution Order

1. `set_env.sh` — defines the new vars + aliases (everything else reads these)
2. `root.hcl` — update HCL local name; reads from `_FRAMEWORK_MAIN_PACKAGE_DIR` with fallback
3. `fw-repo-mgr` — update all var references + generated shim
4. `pkg-mgr` — update `_fw_cfg` function
5. `packages.py` (`config-mgr`) — update with fallback read
6. `framework_config.py` — update with fallback read
7. `config.py` (`fw_repos_diagram_exporter`) — update with fallback read
8. Docs: `config-overview.md`, `config-files.md`
9. Version bump: `_framework-pkg.yaml` + `version_history.md` (after commit sha is known)

## Verification

```bash
cd /home/pyoung/git/pwy-home-lab-pkg
source set_env.sh
echo "_FRAMEWORK_MAIN_PACKAGE=$_FRAMEWORK_MAIN_PACKAGE"
echo "_FRAMEWORK_MAIN_PACKAGE_DIR=$_FRAMEWORK_MAIN_PACKAGE_DIR"
# Should print: pwy-home-lab-pkg and its realpath
echo "_FRAMEWORK_CONFIG_PKG=$_FRAMEWORK_CONFIG_PKG"
echo "_FRAMEWORK_CONFIG_PKG_DIR=$_FRAMEWORK_CONFIG_PKG_DIR"
# Should print same values (legacy aliases)

# Verify realpath resolution (infra/_framework-pkg is a symlink)
ls "$_FRAMEWORK_MAIN_PACKAGE_DIR/_config/config.yaml"
```
