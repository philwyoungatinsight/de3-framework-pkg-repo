# Plan: Framework Config Files in Named Package — via `_framework.yaml`

## Objective

Allow all deployment-specific `framework_*.yaml` files to live in a named package's
`_config/` directory. A single new file, `config/_framework.yaml`, declares which
package is the "config package". `set_env.sh` reads it, exports `_FRAMEWORK_CONFIG_PKG`
(and its dir as `_FRAMEWORK_CONFIG_PKG_DIR`), and all framework tools use that env var
for discovery. A pre-existing `_FRAMEWORK_CONFIG_PKG` env var overrides the file, enabling
per-developer or CI overrides without touching config.

---

## Context

### The design

```
config/_framework.yaml          ← declares which package holds framework config
                                  (the only file that truly cannot move)
set_env.sh                      ← reads _framework.yaml → exports _FRAMEWORK_CONFIG_PKG
                                  and _FRAMEWORK_CONFIG_PKG_DIR; pre-existing env wins
```

Search order for all framework config lookups (lowest → highest priority):
```
1. infra/_framework-pkg/_config/                    framework defaults
2. infra/$_FRAMEWORK_CONFIG_PKG/_config/            named config package (if set)
3. config/                                          ad-hoc/dev overrides (always highest)
```

`config/` stays as the top tier so it remains usable for quick per-developer overrides
without touching the named package's files.

### What this resolves

All four open questions from the previous plan version:

| Question | Resolution |
|----------|-----------|
| Search order | Fixed: `_framework-pkg` → config-pkg → `config/` |
| `framework_backend.yaml` | `set_env.sh` checks `_FRAMEWORK_CONFIG_PKG_DIR/_config/` — no new env var needed |
| `_fw_cfg_path()` / `_fw_cfg()` | Just add one check for `_FRAMEWORK_CONFIG_PKG_DIR/_config/` |
| `framework_packages.yaml` mobility | Can move to the named package — `config/_framework.yaml` is the only true anchor |

### Current callers — no call-site changes needed

All three callers of `find_framework_config_dirs()` pass root = git root; they stay
as-is. `_fw_cfg_path()` and `_fw_cfg()` are internal helpers updated in place.

---

## Open Questions

None — ready to proceed.

---

## Files to Create / Modify

### `config/_framework.yaml` — create

New uber-config file. Declares the config package. The `_` prefix signals
framework-reserved, consistent with `_framework-pkg.yaml`.

```yaml
_framework:
  config_package: pwy-home-lab-pkg
```

Only the `config_package` key is read in this plan. File is extensible for future
framework-level settings that don't belong in any package.

### `infra/_framework-pkg/_framework/_git_root/set_env.sh` — modify

Read `_framework.yaml` and export `_FRAMEWORK_CONFIG_PKG` / `_FRAMEWORK_CONFIG_PKG_DIR`.
A pre-existing `_FRAMEWORK_CONFIG_PKG` env var wins (dev/CI override). Insert after the
existing `_GUI_DIR` / `_CONFIG_DIR` exports and before the `_fw_backend` block:

```bash
# Determine the config package from config/_framework.yaml.
# A pre-existing _FRAMEWORK_CONFIG_PKG env var overrides the file.
if [[ -z "${_FRAMEWORK_CONFIG_PKG:-}" ]]; then
    export _FRAMEWORK_CONFIG_PKG
    _FRAMEWORK_CONFIG_PKG="$(python3 - "$_GIT_ROOT/config/_framework.yaml" <<'EOF'
import sys, yaml, pathlib
p = pathlib.Path(sys.argv[1])
try:
    d = yaml.safe_load(p.read_text()) if p.exists() else {}
    print((d or {}).get('_framework', {}).get('config_package', ''))
except Exception:
    print('')
EOF
)"
fi
export _FRAMEWORK_CONFIG_PKG_DIR=""
if [[ -n "${_FRAMEWORK_CONFIG_PKG:-}" ]]; then
    export _FRAMEWORK_CONFIG_PKG_DIR="$_INFRA_DIR/$_FRAMEWORK_CONFIG_PKG"
fi
```

Also update the `_fw_backend` block (currently two-path) to check the config package dir:

```bash
local _fw_backend
if [[ -f "$_GIT_ROOT/config/framework_backend.yaml" ]]; then
    _fw_backend="$_GIT_ROOT/config/framework_backend.yaml"
elif [[ -n "${_FRAMEWORK_CONFIG_PKG_DIR:-}" && \
        -f "$_FRAMEWORK_CONFIG_PKG_DIR/_config/framework_backend.yaml" ]]; then
    _fw_backend="$_FRAMEWORK_CONFIG_PKG_DIR/_config/framework_backend.yaml"
else
    _fw_backend="$_FRAMEWORK_PKG_DIR/_config/framework_backend.yaml"
fi
```

Note: `config/` is checked first so it remains a valid ad-hoc override location.

### `infra/_framework-pkg/_framework/_utilities/python/framework_config.py` — modify

Update `find_framework_config_dirs()` to insert the config package dir as the middle tier:

```python
def find_framework_config_dirs(root: Path) -> list[Path]:
    """Return ordered list of config dirs containing framework_*.yaml files.

    Search order (lowest to highest priority):
      1. infra/_framework-pkg/_config/             framework defaults
      2. infra/$_FRAMEWORK_CONFIG_PKG/_config/     named config package (if set)
      3. config/                                   ad-hoc/dev overrides

    Files in later dirs override same-named keys from earlier dirs.
    """
    dirs: list[Path] = []

    env_dir = os.environ.get("_FRAMEWORK_PKG_DIR")
    fw_cfg = Path(env_dir) / "_config" if env_dir else root / "infra" / "_framework-pkg" / "_config"
    if fw_cfg.is_dir():
        dirs.append(fw_cfg)

    config_pkg_dir = os.environ.get("_FRAMEWORK_CONFIG_PKG_DIR")
    if config_pkg_dir:
        pkg_cfg = Path(config_pkg_dir) / "_config"
        if pkg_cfg.is_dir() and pkg_cfg not in dirs:
            dirs.append(pkg_cfg)

    override_cfg = root / "config"
    if override_cfg.is_dir() and override_cfg not in dirs:
        dirs.append(override_cfg)

    if not dirs:
        raise FileNotFoundError(f"Framework config dir not found: expected {fw_cfg}")
    return dirs
```

No changes to `find_framework_config_dir()` (backward-compat wrapper) or
`load_framework_config()`.

### `infra/_framework-pkg/_framework/_config-mgr/config_mgr/packages.py` — modify

Update `_fw_cfg_path()` to check the config package dir as the middle tier:

```python
def _fw_cfg_path(repo_root: Path, filename: str) -> Path:
    """Three-path lookup for framework config files.

    Priority (highest first): config/ → _FRAMEWORK_CONFIG_PKG/_config/ → _framework-pkg/_config/
    """
    override = repo_root / "config" / filename
    if override.exists():
        return override
    config_pkg_dir = os.environ.get("_FRAMEWORK_CONFIG_PKG_DIR")
    if config_pkg_dir:
        candidate = Path(config_pkg_dir) / "_config" / filename
        if candidate.exists():
            return candidate
    pkg_dir = os.environ.get("_FRAMEWORK_PKG_DIR") or str(repo_root / "infra" / "_framework-pkg")
    return Path(pkg_dir) / "_config" / filename
```

### `infra/_framework-pkg/_framework/_pkg-mgr/run` — modify

Replace the `_fw_cfg()` shell function body with a three-path check:

```bash
_fw_cfg() {
  local name="$1"
  # config/ is highest priority (ad-hoc overrides)
  [[ -f "$GIT_ROOT/config/$name" ]] && { echo "$GIT_ROOT/config/$name"; return; }
  # Named config package (middle tier)
  if [[ -n "${_FRAMEWORK_CONFIG_PKG_DIR:-}" && \
        -f "$_FRAMEWORK_CONFIG_PKG_DIR/_config/$name" ]]; then
    echo "$_FRAMEWORK_CONFIG_PKG_DIR/_config/$name"; return
  fi
  # _framework-pkg/_config/ fallback
  echo "$_FRAMEWORK_PKG_DIR/_config/$name"
}
```

### `infra/_framework-pkg/_framework/_git_root/root.hcl` — modify

Add the config package dir as a middle tier in the `framework_backend.yaml` lookup:

```hcl
_framework_config_pkg_dir = get_env("_FRAMEWORK_CONFIG_PKG_DIR", "")
_fw_backend_path = (
  fileexists("${local.stack_root}/config/framework_backend.yaml")
  ? "${local.stack_root}/config/framework_backend.yaml"
  : local._framework_config_pkg_dir != "" && fileexists("${local._framework_config_pkg_dir}/_config/framework_backend.yaml")
  ? "${local._framework_config_pkg_dir}/_config/framework_backend.yaml"
  : "${local.stack_root}/infra/_framework-pkg/_config/framework_backend.yaml"
)
_framework_backend = yamldecode(file(local._fw_backend_path))["framework_backend"]
```

### `infra/_framework-pkg/_docs/framework/config-files.md` — modify

- Update the discovery-pattern table to show the three-tier lookup
- Add a section on `config/_framework.yaml` and the `_FRAMEWORK_CONFIG_PKG` env var
- Remove the "no hardcoded paths" claim and replace with accurate description of `config/_framework.yaml` as the one true anchor

### `infra/_framework-pkg/_config/_framework-pkg.yaml` — modify

Bump version to 1.4.6. Append version history entry.

---

## Execution Order

1. `set_env.sh` — exports `_FRAMEWORK_CONFIG_PKG` / `_FRAMEWORK_CONFIG_PKG_DIR`; must run first because all subsequent tools read these env vars
2. `framework_config.py` — update `find_framework_config_dirs()`
3. `packages.py` — update `_fw_cfg_path()`
4. `pkg-mgr/run` — update `_fw_cfg()`
5. `root.hcl` — update `framework_backend.yaml` lookup
6. `config/_framework.yaml` — create the new file
7. `config-files.md` — update docs
8. `_framework-pkg.yaml` — version bump

Step 1 must come before steps 2–5 (they read the env var set_env.sh exports).
Step 6 (create the file) can happen at any point — the code degrades gracefully when
`_FRAMEWORK_CONFIG_PKG` is empty (same two-path behavior as before).

---

## Verification

```bash
source set_env.sh

# _FRAMEWORK_CONFIG_PKG should be set
echo "_FRAMEWORK_CONFIG_PKG=$_FRAMEWORK_CONFIG_PKG"
# Expected: pwy-home-lab-pkg

echo "_FRAMEWORK_CONFIG_PKG_DIR=$_FRAMEWORK_CONFIG_PKG_DIR"
# Expected: .../infra/pwy-home-lab-pkg

# Three dirs returned
python3 -c "
import sys; sys.path.insert(0, 'infra/_framework-pkg/_framework/_utilities/python')
from framework_config import find_framework_config_dirs, load_framework_config
from pathlib import Path
dirs = find_framework_config_dirs(Path('.'))
print('Config dirs:')
for d in dirs: print(' ', d)
"
# Expected: _framework-pkg/_config/, infra/pwy-home-lab-pkg/_config/, config/

# A file placed in pwy-home-lab-pkg/_config/ is found
echo 'framework_validate_config: {test: from-pkg}' \
  > infra/pwy-home-lab-pkg/_config/framework_validate_config.yaml
python3 -c "
import sys; sys.path.insert(0, 'infra/_framework-pkg/_framework/_utilities/python')
from framework_config import find_framework_config_dirs, load_framework_config
from pathlib import Path
cfg = load_framework_config(find_framework_config_dirs(Path('.')))
print('validate_config:', cfg.get('validate_config'))
"
# Expected: {'test': 'from-pkg'}
rm infra/pwy-home-lab-pkg/_config/framework_validate_config.yaml

# config/ still overrides named package (place same key in both, config/ wins)

# pkg-mgr --status still works
infra/_framework-pkg/_framework/_pkg-mgr/run --status

# Override via env var (no _framework.yaml needed)
_FRAMEWORK_CONFIG_PKG=some-other-pkg source set_env.sh
echo "_FRAMEWORK_CONFIG_PKG=$_FRAMEWORK_CONFIG_PKG"
# Expected: some-other-pkg
```
