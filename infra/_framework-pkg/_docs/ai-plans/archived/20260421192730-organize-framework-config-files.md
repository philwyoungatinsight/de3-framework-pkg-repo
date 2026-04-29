# Plan: Organize Framework Config Files — Deployment Overrides via `config/`

## Objective

Reduce clutter in `infra/_framework-pkg/_config/` by moving deployment-specific
`framework_*.yaml` files to `config/` at the git root — the same directory where
`waves_ordering.yaml` already lives as a deployment override. Extend
`load_framework_config()` to search both `_framework-pkg/_config/` (framework defaults)
and `config/` (deployment overrides) so tools find files wherever they live.

No new env vars. No hardcoded package names in framework code.

---

## Context

### Current `_framework-pkg/_config/` static files

| File | Category | Move target |
|---|---|---|
| `_framework-pkg.yaml` | framework | stays |
| `framework_config_mgr.yaml` | framework | stays |
| `framework_package_management.yaml` | framework-operational | stays (pkg-mgr hardcodes path) |
| `framework_package_repositories.yaml` | framework-operational | stays (pkg-mgr hardcodes path) |
| `framework_packages.yaml` | **anchor** | ALWAYS stays |
| `framework_backend.yaml` | **deployment** | → `config/` |
| `framework_ansible_inventory.yaml` | deployment | → `config/` |
| `framework_clean_all.yaml` | deployment | → `config/` |
| `framework_ephemeral_dirs.yaml` | deployment | → `config/` |
| `framework_external_capabilities.yaml` | deployment | → `config/` |
| `framework_manager.yaml` | deployment | → `config/` |
| `framework_pre_apply_unlock.yaml` | deployment | → `config/` |
| `framework_validate_config.yaml` | deployment | → `config/` |
| `gcp_seed.yaml` | deployment | → `config/` |
| `gcp_seed_secrets.sops.yaml` | deployment | → `config/` |
| `waves_ordering.yaml` | deployment | → `config/` (already auto-discovered there by `run`) |

### How the `config/` dir is already used

`run` (the wave runner) already checks `config/waves_ordering.yaml` first (line 278),
then falls back to `infra/*/_config/waves_ordering.yaml`. This is the exact pattern
to extend — `config/` at git root is the deployment override layer.

### How files are currently found

| File / group | Finder |
|---|---|
| `framework_*.yaml` (all) | `load_framework_config()` in `framework_config.py` — globs ONE dir |
| `framework_packages.yaml` | `packages.py` hardcodes `$_FRAMEWORK_PKG_DIR/_config/framework_packages.yaml` |
| `framework_config_mgr.yaml` | `packages.py` hardcodes `$_FRAMEWORK_PKG_DIR/_config/framework_config_mgr.yaml` |
| `framework_backend.yaml` | `root.hcl` hardcodes `infra/_framework-pkg/_config/framework_backend.yaml` |
| `waves_ordering.yaml` | `run` script searches `config/waves_ordering.yaml` first — **already flexible** |
| `framework_package_management.yaml` | `pkg-mgr/run` hardcodes `$_FRAMEWORK_PKG_DIR/_config/...` |
| `framework_package_repositories.yaml` | `pkg-mgr/run` hardcodes `$_FRAMEWORK_PKG_DIR/_config/...` |

### What does NOT need to change

- `framework_packages.yaml`, `framework_config_mgr.yaml` — hardcoded in `packages.py`; stay in `_framework-pkg/_config/`
- `framework_package_management.yaml`, `framework_package_repositories.yaml` — hardcoded in `pkg-mgr/run`; stay
- `_framework-pkg.yaml` — version file; stays
- `waves_ordering.yaml` — `run` already finds it in `config/`; just needs the `git mv`
- `config_source` on `_framework-pkg` — not needed; the `config_source` mechanism routes `unit_params`
  config, not framework config files. A different mechanism is right here.

### Design

`find_framework_config_dirs()` returns two dirs, in order:
1. `$_FRAMEWORK_PKG_DIR/_config/` (framework defaults)
2. `$GIT_ROOT/config/` (deployment overrides — keys here win)

`load_framework_config()` updated to accept a list of dirs; merges in order (later overrides earlier).

`root.hcl` uses HCL `fileexists()` to check `config/framework_backend.yaml` first,
falling back to `_framework-pkg/_config/framework_backend.yaml`. No env vars.

---

## Open Questions

None — ready to proceed.

---

## Files to Create / Modify

### `infra/_framework-pkg/_framework/_utilities/python/framework_config.py` — modify

Replace `find_framework_config_dir()` (single Path) with `find_framework_config_dirs()`
(list of Paths: framework first, `config/` second). Keep `find_framework_config_dir()` as
a backward-compat wrapper. Update `load_framework_config()` to accept a single Path or list.

```python
"""Load split framework_*.yaml config files into a unified dict.

Usage:
    from framework_config import load_framework_config, find_framework_config_dirs

    dirs = find_framework_config_dirs(git_root)
    fw = load_framework_config(dirs)
    bucket = fw["backend"]["config"]["bucket"]
"""
from __future__ import annotations
import os
from pathlib import Path

try:
    import yaml
except ImportError:
    raise ImportError("pyyaml not found — run: pip install pyyaml")


def find_framework_config_dirs(root: Path) -> list[Path]:
    """Return ordered list of config dirs containing framework_*.yaml files.

    Framework dir is first (defaults); git-root config/ is second (overrides).
    Files in later dirs override same-named keys from earlier dirs.
    """
    dirs: list[Path] = []

    env_dir = os.environ.get("_FRAMEWORK_PKG_DIR")
    fw_cfg = Path(env_dir) / "_config" if env_dir else root / "infra" / "_framework-pkg" / "_config"
    if fw_cfg.is_dir():
        dirs.append(fw_cfg)

    override_cfg = root / "config"
    if override_cfg.is_dir() and override_cfg != fw_cfg:
        dirs.append(override_cfg)

    if not dirs:
        raise FileNotFoundError(f"Framework config dir not found: expected {fw_cfg}")
    return dirs


def find_framework_config_dir(root: Path) -> Path:
    """Backward-compat: return the primary (framework) config dir."""
    return find_framework_config_dirs(root)[0]


def load_framework_config(config_dir_or_dirs) -> dict:
    """Read all framework_*.yaml files and assemble a flat framework dict.

    Accepts a single Path (backward-compat) or a list of Paths.
    Files in later dirs override same-named keys from earlier dirs.
    Secrets files (containing 'secrets') are excluded.
    """
    if isinstance(config_dir_or_dirs, Path):
        dirs = [config_dir_or_dirs]
    else:
        dirs = list(config_dir_or_dirs)

    result: dict = {}
    for config_dir in dirs:
        for f in sorted(config_dir.glob("framework_*.yaml")):
            if "secrets" in f.name:
                continue
            try:
                raw = yaml.safe_load(f.read_text())
            except yaml.YAMLError:
                continue
            if not isinstance(raw, dict):
                continue
            for k, v in raw.items():
                if k.startswith("framework_"):
                    result[k[len("framework_"):]] = v
    return result
```

### `infra/_framework-pkg/_framework/_git_root/run` — modify

Update the `load_framework_config` call to use `find_framework_config_dirs`:

```python
# Change import (around line 94):
from framework_config import find_framework_config_dirs, load_framework_config

# Change call (around line 230):
cfg = load_framework_config(find_framework_config_dirs(STACK_ROOT))
```

### `infra/_framework-pkg/_framework/_clean_all/run` — investigate then modify

Read the file to find how it loads framework config (around line 100). Update to use
`find_framework_config_dirs()`. The import path for framework_config.py is already in
sys.path via `_utilities/python`.

### `infra/_framework-pkg/_framework/_utilities/python/validate-config.py` — modify

Already calls `find_framework_config_dir()` + `load_framework_config()`. Update to
`find_framework_config_dirs()`:

```python
# Change import to include find_framework_config_dirs
# Change call:
return load_framework_config(find_framework_config_dirs(root))
```

### `infra/_framework-pkg/_framework/_git_root/root.hcl` — modify

Change line ~57 from hardcoded `_framework-pkg/_config/` to check `config/` first:

```hcl
# Replace:
_framework_backend = yamldecode(file("${local.stack_root}/infra/_framework-pkg/_config/framework_backend.yaml"))["framework_backend"]

# With:
_fw_backend_path   = (
  fileexists("${local.stack_root}/config/framework_backend.yaml")
  ? "${local.stack_root}/config/framework_backend.yaml"
  : "${local.stack_root}/infra/_framework-pkg/_config/framework_backend.yaml"
)
_framework_backend = yamldecode(file(local._fw_backend_path))["framework_backend"]
```

### Move deployment-specific files — `git mv`

```bash
DEPLOY_CFG="config"
FW_CFG="infra/_framework-pkg/_config"

git mv "$FW_CFG/framework_backend.yaml"               "$DEPLOY_CFG/"
git mv "$FW_CFG/framework_ansible_inventory.yaml"     "$DEPLOY_CFG/"
git mv "$FW_CFG/framework_clean_all.yaml"             "$DEPLOY_CFG/"
git mv "$FW_CFG/framework_ephemeral_dirs.yaml"        "$DEPLOY_CFG/"
git mv "$FW_CFG/framework_external_capabilities.yaml" "$DEPLOY_CFG/"
git mv "$FW_CFG/framework_manager.yaml"               "$DEPLOY_CFG/"
git mv "$FW_CFG/framework_pre_apply_unlock.yaml"      "$DEPLOY_CFG/"
git mv "$FW_CFG/framework_validate_config.yaml"       "$DEPLOY_CFG/"
git mv "$FW_CFG/gcp_seed.yaml"                        "$DEPLOY_CFG/"
git mv "$FW_CFG/gcp_seed_secrets.sops.yaml"           "$DEPLOY_CFG/"
git mv "$FW_CFG/waves_ordering.yaml"                  "$DEPLOY_CFG/"
```

Note: `waves_ordering.yaml` is already auto-discovered in `config/` by `run` — no code change needed there.

### `infra/_framework-pkg/_config/_framework-pkg.yaml` — modify

Bump version `1.4.2` → `1.4.3`. Append version history entry (sha filled in after commit):

```yaml
# _framework-pkg: 1.4.3  (2026-04-21, git: TBD)
# - framework_config.py: find_framework_config_dirs() — framework dir + config/ at git root
# - load_framework_config(): accepts list of dirs; deployment overrides framework defaults
# - root.hcl: framework_backend.yaml checked in config/ first, _framework-pkg/_config/ fallback
# - deployment-specific framework_*.yaml files moved from _framework-pkg/_config/ to config/
```

---

## Execution Order

1. Modify `framework_config.py` — add `find_framework_config_dirs()`, update `load_framework_config()`
2. Modify callers: `run` (wave runner), `clean_all/run`, `validate-config.py`
3. Modify `root.hcl` — add `fileexists()` two-path lookup for `framework_backend.yaml`
4. Move files (`git mv`) — only after all callers are updated; verify `config/` dir exists
5. Bump `_framework-pkg.yaml` version to 1.4.3

Steps 1–3 must complete before Step 4. Moving files before callers are updated will break tools.

---

## Verification

```bash
source set_env.sh

# framework config dirs should show both dirs
python3 -c "
import sys; sys.path.insert(0, 'infra/_framework-pkg/_framework/_utilities/python')
from framework_config import find_framework_config_dirs, load_framework_config
from pathlib import Path
dirs = find_framework_config_dirs(Path('.'))
print('Config dirs:', [str(d) for d in dirs])
cfg = load_framework_config(dirs)
print('backend type:', cfg.get('backend', {}).get('type'))
print('waves_ordering present:', 'waves_ordering' in cfg)
print('ansible_inventory present:', 'ansible_inventory' in cfg)
"

# config-mgr should regenerate without errors
infra/_framework-pkg/_framework/_config-mgr/generate

# pkg-mgr status should still work
infra/_framework-pkg/_framework/_pkg-mgr/run --status

# waves_ordering.yaml should be found by the run script
python3 -c "
from pathlib import Path
p = Path('config/waves_ordering.yaml')
print('waves_ordering found at config/:', p.exists())
"

# root.hcl framework_backend resolved correctly (check via terragrunt plan in any unit)
```
