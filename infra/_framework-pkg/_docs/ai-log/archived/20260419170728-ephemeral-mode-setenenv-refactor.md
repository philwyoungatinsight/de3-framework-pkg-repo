# ephemeral --mode flag, set_env.sh function refactor, HWE monitor out-of-/tmp fix

## Summary

Added `--mode` flag to the ephemeral RAM-drive framework so directory permissions are
configurable alongside size and ownership. Refactored `set_env.sh` into named functions
for readability and wired `framework/ephemeral/run` to fire automatically whenever
`validate-config.py` actually executes (rate-limited by its existing flag file). Also
moved HWE monitor scripts out of `/tmp` into `$_DYNAMIC_DIR` to comply with the
no-out-of-repo-paths rule.

## Changes

- **`set_env.sh`** — refactored flat script into three named functions
  (`_set_env_export_vars`, `_set_env_create_dirs`, `_set_env_run_startup_checks`);
  `exit 1` → `return 1` for sourced-script correctness; ephemeral/run now auto-called
  when validate-config fires (detected via flag-file mtime < 5s, cross-platform via Python)
- **`framework/ephemeral/ephemeral.sh`** — added `--mode` / `DIR_MODE` flag; `get_current_mode()` and `set_mode()` helpers; `NEEDS_CHMOD` branch for mode-only updates without remount; replaced Linux `mount --move` approach with staging-in-`/dev/shm` + umount + fresh mount for size changes; path resolution now uses `realpath` with a `dirname/basename` fallback (avoids `cd` into root-owned 0700 dirs)
- **`framework/ephemeral/run`** — reads `mode` field from YAML config; passes `--mode` to `ephemeral.sh` when set
- **`framework/ephemeral/README.md`** — updated to document `--mode` flag, new idempotent-update behavior, and revised "how it works" flow
- **`config/framework.yaml`** — improved ephemeral_dirs field documentation; added explicit `size_mb: 64` to the default entry
- **`infra/maas-pkg/_modules/maas_machine/main.tf`** — HWE monitor script and log moved from `/tmp/clear-hwe-$ID.*` to `$_DYNAMIC_DIR/hwe-monitor/clear-hwe-$ID.*`
- **`run`** — minor docstring fix (`~/.run-waves-logs/` → `$_WAVE_LOGS_DIR`)
- **`docs/TODO.md`** — pruned completed items

## Notes

The mtime-based validate-config detection uses a 5-second window. This is intentionally
generous — if the machine is very slow and validate-config takes >5s, ephemeral/run won't
be triggered. In practice validate-config runs in <1s so this is fine.
