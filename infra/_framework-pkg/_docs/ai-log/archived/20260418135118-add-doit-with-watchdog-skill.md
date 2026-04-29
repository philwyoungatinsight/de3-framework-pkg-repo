# Add /doit-with-watchdog Skill

**Date**: 2026-04-18
**Plan**: `docs/ai-plans/archived/20260418135118-add-doit-with-watchdog-skill.md`

## What was done

Created `.claude/commands/doit-with-watchdog.md` — a new skill that combines `/doit`
plan execution with the build watchdog cron job.

The skill:
1. Parses `<plan-name>` and optional `[polling-minutes]` (default 2) from arguments
2. Resolves runtime paths via `set_env.sh`
3. Registers the build watchdog cron job (idempotent — skips if already running)
4. Executes the named ai-plan (Steps 8–10 of `/doit`)
5. Archives the plan and ships via `/ship`
6. Stops the watchdog via `CronDelete`

The cron expression is derived from the polling interval: `*/N * * * *`.
All paths in the cron prompt are substituted with literal resolved values at registration
time (not shell variables), matching the pattern in `/watchdog`.
