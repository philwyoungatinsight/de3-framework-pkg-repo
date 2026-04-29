# Plan: Consolidate Framework Settings 3-Tier Resolution

## Objective

Add a `config-mgr fw-setting <filename>` subcommand that prints the resolved path to a
framework settings file using the canonical 3-tier lookup. Replace the copy-pasted inline
bash in `ramdisk-mgr` with a single call to this command. Fix `unit-mgr`'s broken
`_read_framework_backend()` which reads from the wrong path (no `_framework_settings/`
subdirectory, no 3-tier). The 3-tier logic then lives in exactly one place: `packages.py::_fw_cfg_path()`.

## Context

The 3-tier resolution order for framework settings files is:
1. `$GIT_ROOT/config/<filename>` — per-developer override
2. `$_FRAMEWORK_CONFIG_PKG_DIR/_config/_framework_settings/<filename>` — consumer package
3. `$_FRAMEWORK_PKG_DIR/_config/_framework_settings/<filename>` — framework default

**Existing correct implementations:**
- `packages.py::_fw_cfg_path(repo_root, filename)` — the canonical Python implementation,
  used internally by `config-mgr` for `framework_packages.yaml` and `framework_config_mgr.yaml`
- `framework_config.py::find_framework_config_dirs()` — similar logic, used by `clean-all`
  and `validate-config.py` via `load_framework_config()`
- `set_env.sh` — inline bash 3-tier for `framework_backend.yaml` only (cannot use
  `config-mgr` — runs before config-mgr is in PATH; must stay as-is)

**Broken / duplicated implementations to fix:**
- `ramdisk-mgr` — has inline bash 3-tier in TWO places (setup mode and teardown mode);
  uses `"$_CONFIG_MGR" fw-setting framework_ramdisk` after this plan
- `unit-mgr/main.py::_read_framework_backend()` — reads from
  `$_FRAMEWORK_PKG_DIR/_config/framework_backend.yaml` (missing `_framework_settings/`,
  no 3-tier); should use `_fw_cfg_path()`

**Not touched:**
- `set_env.sh` — correct and necessary; cannot use `config-mgr` (runs before PATH is set)
- `clean-all`, `validate-config.py` — already use `load_framework_config(find_framework_config_dirs())`
  which is the right approach for bulk-loading all settings; no change needed
- `generate-inventory` — separate concern, reads from single dir by design

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/_framework-pkg/_framework/_config-mgr/config_mgr/main.py` — modify

Add `cmd_fw_setting` function and register it as the `fw-setting` subcommand.

The function calls `_fw_cfg_path()` from `packages.py` (already imported) and prints the
absolute path. The argument is the filename, with or without `.yaml` suffix; normalise to
always add `.yaml` if absent.

```python
def cmd_fw_setting(args: argparse.Namespace) -> None:
    repo_root = _repo_root()
    name = args.name
    if not name.endswith(".yaml"):
        name = name + ".yaml"
    path = _fw_cfg_path(repo_root, name)
    if not path.exists():
        sys.exit(f"config-mgr: fw-setting: file not found after 3-tier lookup: {path}")
    print(path)
```

Import `_fw_cfg_path` at the top of `main.py` — it is already in `packages.py` but not
currently imported into `main.py`. Add it to the existing import from `.packages`:

```python
from .packages import (
    _fw_cfg_path,          # add this
    load_framework_packages,
    pkg_yaml_path,
    resolve_config_source,
)
```

Add the subparser in `_build_parser()` before the `return p` line:

```python
    # fw-setting
    fw = sub.add_parser(
        "fw-setting",
        help="Print the resolved path to a framework settings file",
        description=(
            "Resolve a framework settings filename through the 3-tier lookup\n"
            "(per-dev config/ → consumer _framework_settings/ → framework default)\n"
            "and print the absolute path of the winning file.\n\n"
            "Useful in bash scripts to avoid duplicating the lookup logic:\n"
            "  YAML=$(config-mgr fw-setting framework_ramdisk)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  config-mgr fw-setting framework_ramdisk\n"
            "  config-mgr fw-setting framework_ramdisk.yaml\n"
            "  config-mgr fw-setting framework_clean_all\n"
        ),
    )
    fw.add_argument(
        "name",
        metavar="FILENAME",
        help="Framework settings filename, e.g. framework_ramdisk or framework_ramdisk.yaml",
    )
```

Add `"fw-setting": cmd_fw_setting` to the `dispatch` dict in `main()`.

### `infra/_framework-pkg/_framework/_ramdisk-mgr/ramdisk-mgr` — modify

Replace the two inline 3-tier bash blocks (one in setup mode, one in teardown mode) with
a single call to `config-mgr fw-setting`. Both blocks currently look like:

```bash
    if [[ -f "$_GIT_ROOT/config/framework_ramdisk.yaml" ]]; then
        RAMDISK_YAML="$_GIT_ROOT/config/framework_ramdisk.yaml"
    elif [[ -n "${_FRAMEWORK_CONFIG_PKG_DIR:-}" && \
            -f "$_FRAMEWORK_CONFIG_PKG_DIR/_config/_framework_settings/framework_ramdisk.yaml" ]]; then
        RAMDISK_YAML="$_FRAMEWORK_CONFIG_PKG_DIR/_config/_framework_settings/framework_ramdisk.yaml"
    else
        RAMDISK_YAML="$_FRAMEWORK_PKG_DIR/_config/_framework_settings/framework_ramdisk.yaml"
    fi
```

Replace each with:

```bash
    RAMDISK_YAML="$("$_CONFIG_MGR" fw-setting framework_ramdisk)"
```

`$_CONFIG_MGR` is already exported by `set_env.sh` (which is sourced at the top of both
modes) so no additional sourcing is needed.

### `infra/_framework-pkg/_framework/_unit-mgr/unit_mgr/main.py` — modify

`_read_framework_backend()` currently reads from the wrong path:

```python
candidate = Path(pkg_dir) / "_config" / "framework_backend.yaml"
```

Replace with a call to `_fw_cfg_path()` from `packages.py`. Import it at the top of
`unit_mgr/main.py`:

```python
from .packages import _fw_cfg_path   # or wherever packages is relative to unit_mgr
```

Wait — `unit-mgr` has its own `packages.py`? Check. If not, import from the framework
utilities path. Looking at the code, `unit_mgr/main.py` currently does its own
`_read_framework_backend` without using the shared `_fw_cfg_path`. The fix is to reuse
the already-correct `_fw_cfg_path` from `config-mgr/packages.py`.

Since `unit-mgr` and `config-mgr` are sibling tools, share via the utilities path. Add
`_fw_cfg_path` to `_utilities/python/framework_config.py` as a re-export, or simply
duplicate the implementation in `unit_mgr/packages.py` if that file exists.

**Check during execution**: run `ls infra/_framework-pkg/_framework/_unit-mgr/unit_mgr/`
to see if a `packages.py` exists there. If yes, add `_fw_cfg_path` there. If no, add it
directly in `unit_mgr/main.py`.

Replace the body of `_read_framework_backend()`:

```python
def _read_framework_backend(repo_root: Path) -> dict:
    path = _fw_cfg_path(repo_root, "framework_backend.yaml")
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("framework_backend", {})
```

Also fix the two error messages that still reference the old path
(`"infra/_framework-pkg/_config/framework_backend.yaml"`) — remove the hardcoded path
from the error text since the resolved path will vary.

## Execution Order

1. **`config-mgr/main.py`** — add `_fw_cfg_path` import + `cmd_fw_setting` function +
   `fw-setting` subparser + dispatch entry. This is the foundation; do it first.
2. **`ramdisk-mgr`** — replace both 3-tier bash blocks. Depends on step 1.
3. **`unit-mgr/main.py`** — fix `_read_framework_backend()`. Independent of steps 1–2
   but do it last so the `fw-setting` smoke-test in verification comes first.

## Verification

```bash
# After step 1: smoke-test the new subcommand
source set_env.sh
config-mgr fw-setting framework_ramdisk
# → should print .../infra/pwy-home-lab-pkg/_config/_framework_settings/framework_ramdisk.yaml
#   (consumer override wins over framework default)

config-mgr fw-setting framework_clean_all
# → should print .../infra/pwy-home-lab-pkg/_config/_framework_settings/framework_clean_all.yaml
#   (consumer override exists)

config-mgr fw-setting framework_ansible_inventory
# → should print .../infra/_framework-pkg/_config/_framework_settings/framework_ansible_inventory.yaml
#   (no consumer override → falls back to framework default)

# After step 2: ramdisk-mgr still runs correctly
ramdisk-mgr --setup   # should skip (size_mb: 0 in consumer override)

# After step 3: unit-mgr no longer reads from wrong path (no direct test, code review only)
```
