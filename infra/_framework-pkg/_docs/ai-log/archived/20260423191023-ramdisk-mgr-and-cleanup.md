# refactor: rename ephemeral → ramdisk-mgr; consolidate to single script

**Date**: 2026-04-23

## What changed

### ramdisk-mgr (replaces two ephemeral scripts)

- **`_framework/_ramdisk-mgr/ramdisk-mgr`** — new single executable replacing the old
  `_ephemeral/ephemeral` + `_ephemeral/ephemeral.sh` pair. Two modes:
  - `--setup` (default, no args): reads `framework_ramdisk.yaml` and mounts all declared dirs
  - `--path <dir> [options]`: mounts/configures a single directory as a RAM drive
  All mount, resize, ownership, and staging logic from `ephemeral.sh` is inlined.
- **`_framework/_ephemeral/`** — directory deleted (ephemeral, ephemeral.sh, README.md)
- **`_config/_framework_settings/framework_ramdisk.yaml`** — replaces
  `framework_ephemeral_dirs.yaml`; top-level key is `framework_ramdisk`; env var renamed
  to `_RAMDISK_DIR`
- **`_config/_framework_settings/framework_ephemeral_dirs.yaml`** — deleted
- **`_framework/_human-only-scripts/setup-ephemeral-dirs/`** — deleted; replaced by
  `ramdisk-mgr --setup`

### set_env.sh and run

- `_EPHEMERAL` → `_RAMDISK_MGR` pointing to `_ramdisk-mgr/ramdisk-mgr`
- `_EPHEMERAL_DIR` → `_RAMDISK_DIR` at `$_DYNAMIC_DIR/ramdisk`
- `_set_env_update_path`: `_ephemeral` → `_ramdisk-mgr`
- `_set_env_create_dirs`: `$_EPHEMERAL_DIR` → `$_RAMDISK_DIR`
- `_git_root/run` Python: `_EPHEMERAL_RUN` → `_RAMDISK_MGR_BIN`

### gpg-mgr — GNU-style args

- Positional subcommands (`check`, `unlock`) replaced with `-e|--ensure`, `-c|--check`,
  `-u|--unlock`; `set_env.sh` updated to call `gpg-mgr --ensure`

### sops-mgr

- New `_framework/_sops-mgr/sops-mgr` (replaces ad-hoc scripts at
  `_human-only-scripts/sops/`)
- Old `re-encrypt-sops-files.sh` and `verify-encryption.sh` deleted

### config-mgr

- `config_mgr/main.py`: improved argparse help text with examples and descriptions
- New `_framework/_config-mgr/README.md`: comprehensive usage docs

### CLAUDE.md

- Added GNU argument style convention
- Updated script naming example: `ephemeral` → `ramdisk-mgr`
- Updated framework tool locations reference: `_ephemeral/` → `_ramdisk-mgr/`

### Other cleanup

- `_docs/ai-plans/move-gpg-key-unlock-to-fw.md` — deleted (work completed)
- `_human-only-scripts/gpg/README.gpg-setup.md` — moved to
  `pwy-home-lab-pkg/_docs/tech-debt/gpg/` as a tech-debt note
- `framework_repo_manager.yaml` — added comment block; set `framework_repo_dir` to
  `git/de3-generated-framework-repos`
- `pwy-home-lab-pkg.yaml` — minor: single-line `_unit_purpose` strings (no multiline)
