# Remove hardcoded paths from /watchdog skill

**Date**: 2026-04-18

## What changed

Rewrote `.claude/commands/watchdog.md` to eliminate four hardcoded references to the old
repo path `/home/pyoung/git/pwy-home-lab/...` and the stale log path `~/.build-watchdog.log`.

### Changes in `.claude/commands/watchdog.md`

- **Added Step 0**: runs `git rev-parse --show-toplevel` + `source set_env.sh` to resolve
  `GIT_ROOT`, `WATCHDOG_SCRIPT`, `WATCHDOG_LOG`, and `WATCHDOG_REPORT` at skill-invocation time.
- **Renumbered** old Step 0 (session argument parsing) to Step 0.5.
- **Step 2 cron prompt**: added explicit instruction to substitute literal resolved paths
  before passing to `CronCreate` (shell variables don't expand at cron fire time).
- **Steps 2, 3, 4**: replaced all hardcoded paths with `${WATCHDOG_SCRIPT}`,
  `${WATCHDOG_LOG}`, and `${WATCHDOG_REPORT}` references.
- **Log path**: corrected from `~/.build-watchdog.log` to `${_DYNAMIC_DIR}/watchdog/build-watchdog.log`.

## Why

The cron job was silently failing because the bash invocation pointed at a path in the old
repo (`pwy-home-lab`) that doesn't exist. The skill now derives all paths at runtime so it
works in any checkout location.
