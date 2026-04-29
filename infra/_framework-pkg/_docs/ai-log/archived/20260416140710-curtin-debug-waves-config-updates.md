# Curtin debug logging, waves config fixes, README updates

## Summary

Added `aa_debug` late_command to Rocky 9 curtin templates to capture environment
state early and write a progress log to the target disk. Removed spurious
`skip_on_clean: true` from two PXE waves. Updated README stubs for
`scripts/ai-only-scripts/` subdirectories and added a TODO item for renaming
the `skip_on_clean` parameter.

## Changes

- **`infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/templates/curtin_userdata_rocky9.j2`**
  and **`infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/templates/curtin_userdata_rocky9.j2`**
  — Added `aa_debug` late_command (runs first alphabetically) that captures disk
  layout, mounts, and environment at the start of late_commands, writing a progress
  log to `/tmp/curtin-late.log` and copying it to `$TARGET/var/log/curtin-late-debug.log`.
  Made `copy_ssh_keys` and other intermediate commands non-fatal so `zz_signal_maas`
  always runs.

- **`config/waves_ordering.yaml`** — Removed `skip_on_clean: true` from
  `pxe.maas.seed-server` and `pxe.maas.test-vms` waves (both now use the bare
  list-item format without skip flags).

- **`docs/TODO.md`** — Added TODO item to rename `skip_on_clean` button/parameter
  to `_ignore_on_wave_run` with a description of the intended semantics.

- **`scripts/ai-only-scripts/archived/README.md`** — Added content explaining that
  this directory holds scripts that can probably be removed.

- **`scripts/ai-only-scripts/build-watchdog/README.md`** — Added content documenting
  the build-watchdog scripts (`check` for cron, `run` for interactive monitoring).

- **`infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg_secrets.sops.yaml`** — Secrets
  update (encrypted).
