# Update claude-skills.md to Document All Current Skills

## Summary

`docs/claude-skills.md` was missing four skills (`/doit-with-watchdog`, `/watchdog-off`,
`/work-on-maas`, `/annihilate-maas-machine`) and had stale details for `/watchdog`
(old log paths, wrong cron schedule, missing Step 0 path resolution). Updated to cover
all 8 skills with accurate algorithms.

## Changes

- **`docs/claude-skills.md`** — added `/doit-with-watchdog`, `/watchdog-off`, `/work-on-maas`,
  `/annihilate-maas-machine` sections; updated `/doit` to document resume mode and archive step;
  updated `/watchdog` to reflect runtime path resolution, correct `*/2` schedule, and report
  structure; updated `/ship` to include archive step

## Notes

The GUI `homelab_gui.py` has unrelated in-progress changes from the `gui-gcs-sync-loading-steps`
plan — excluded from this commit.
