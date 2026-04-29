# /ship: Archive ai-log Files Older Than 3 Days

## Summary

`/ship` now archives ai-log files older than 3 days to `docs/ai-log/archived/` as part
of each ship run. The timestamp in the filename is parsed to determine age (not filesystem
mtime). Files are moved with `git mv` so the rename appears atomically in the ship commit.

## Changes

- **`.claude/commands/ship.md`** — added Step 5 (archive old ai-logs) between the
  ai-log-summary update and the stage/commit step; renumbered stage/commit to Step 6
  and push to Step 7; updated the stage/commit include list to mention archived files

- **`docs/ai-log/archived/.gitkeep`** — created the directory so git tracks it

- **`docs/ai-log/archived/`** — initial bulk archive of 62 ai-log files older than
  2026-04-11 (3 days before today 2026-04-14)
