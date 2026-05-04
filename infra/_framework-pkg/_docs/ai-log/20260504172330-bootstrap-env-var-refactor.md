# Bootstrap Env-Var Refactor: _FRAMEWORK_PKG_DIR + _MAIN_PKG_DIR as Primary Anchors

## Summary

Replaced the fragile `_GIT_ROOT`-based env-var bootstrap with a clean two-anchor
system: `_FRAMEWORK_PKG_DIR` (always computable from `BASH_SOURCE[0]`, never needs
`git rev-parse`) and `_MAIN_PKG_DIR` (replaces `_FRAMEWORK_MAIN_PACKAGE_DIR`). All
legacy aliases (`_GIT_ROOT`, `_FRAMEWORK_MAIN_PACKAGE_DIR`, `_FRAMEWORK_CONFIG_PKG`,
`_FRAMEWORK_CONFIG_PKG_DIR`) are removed from exports. The root cause of the bug
(tools `cd SCRIPT_DIR` before running Python, causing `git rev-parse` to return the
framework repo root instead of the consumer repo root) is fully addressed.

## Changes

- **`set_env.sh`** — primary anchor is now `_FRAMEWORK_PKG_DIR` from `BASH_SOURCE[0]`;
  `_repo_root` is a local-only variable; `_MAIN_PKG_DIR` replaces
  `_FRAMEWORK_MAIN_PACKAGE_DIR`; idempotency guard updated; no legacy aliases exported
- **`config_mgr/main.py`**, **`unit_mgr/main.py`**, **`fw_repos_diagram_exporter/config.py`** —
  `_repo_root()` now checks `_FRAMEWORK_PKG_DIR` first; `_GIT_ROOT` fallback removed
- **`framework_config.py`**, **`config_mgr/packages.py`**, **`validate-config.py`** —
  `_FRAMEWORK_MAIN_PACKAGE_DIR` → `_MAIN_PKG_DIR` in all env reads
- **`config-mgr`**, **`unit-mgr`**, **`fw-repos-diagram-exporter`**, **`pkg-mgr`**,
  **`generate-inventory/run`** — set `_FRAMEWORK_PKG_DIR` from `SCRIPT_DIR/../..`
  before sourcing `set_env.sh`; no longer call `git rev-parse`
- **`ramdisk-mgr`** — sets `_FRAMEWORK_PKG_DIR` at top; both `GIT_ROOT` derivations
  use `dirname(dirname(_FRAMEWORK_PKG_DIR))`
- **`framework-utils.sh`** — sources `set_env.sh` via `_FRAMEWORK_PKG_DIR` with `:?` guard;
  `_find_component_config` uses `_FRAMEWORK_PKG_DIR` to get git root
- **`maas-state-cache.sh`** — `_maas_state_git_root()` checks `_FRAMEWORK_PKG_DIR` first
- **`wave-mgr`** — `_GIT_ROOT` bootstrap and `_source_env()` both check
  `_FRAMEWORK_PKG_DIR` before falling back to `git rev-parse`
- **`fw-repo-mgr`** — `_git_root()` checks `_FRAMEWORK_PKG_DIR` first; shim generator
  drops legacy aliases; all `_FRAMEWORK_MAIN_PACKAGE_DIR` → `_MAIN_PKG_DIR`
- **`root.hcl`** — `get_env("_MAIN_PKG_DIR", "")` replaces old var name

## Root Cause

All bash tool wrappers (`config-mgr`, `unit-mgr`, etc.) do `cd SCRIPT_DIR && exec python3`,
changing CWD to the framework package directory. Any `git rev-parse --show-toplevel`
inside Python then resolved to the framework repo (or its ext-packages clone), not the
consumer repo. Tools that relied on `_GIT_ROOT` as a fallback only worked if the parent
shell had already sourced `set_env.sh`. Tools run cold (e.g., by CI) would silently use
the wrong root.

## Notes

- `_FRAMEWORK_PKG_DIR` is always derivable from `BASH_SOURCE[0]` without I/O — no git call needed
- `_MAIN_PKG_DIR` is still config-derived (reads `config/_framework.yaml`) but set once in set_env.sh
- Consumer `run` scripts already used `Path(__file__).parent.resolve()` in ext-packages;
  only `de3-pwy-home-lab-pkg-repo/run` still had `git rev-parse` — fixed
