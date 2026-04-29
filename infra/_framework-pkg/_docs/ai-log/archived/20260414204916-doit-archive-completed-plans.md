# /doit: Archive Completed Plans to docs/ai-plans/archived/

## Summary

After a plan is executed, `/doit` now moves the plan file to `docs/ai-plans/archived/`
with a timestamp prefix (same convention as ai-log files), staged atomically as part of
the `/ship` commit. This keeps `docs/ai-plans/` clean — only in-progress plans live there.

## Changes

- **`.claude/commands/doit.md`** — added Step 9 (archive plan) and Step 10 (ship);
  execution step renumbered from 8 to 8, archive is a new Step 9, ship is Step 10.
  Archive command: `mv docs/ai-plans/<name>.md docs/ai-plans/archived/$(date +%Y%m%d%H%M%S)-<name>.md`

- **`docs/ai-plans/archived/.gitkeep`** — created the directory so git tracks it before
  any plans are archived into it
