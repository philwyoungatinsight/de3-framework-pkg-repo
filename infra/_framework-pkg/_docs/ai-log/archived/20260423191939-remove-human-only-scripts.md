# Remove human-only-scripts feature

**Plan**: `remove-ho-scripts`

## What was done

The `_human-only-scripts` directory concept is removed. The directory was already empty
(user had removed the scripts). All references in live code and docs were cleaned up.

## Changes

- **Deleted**: `infra/_framework-pkg/_framework/_human-only-scripts/` (empty dir removed)
- **Modified**: `infra/_framework-pkg/_framework/README.md` — removed `_human-only-scripts/` table row
- **Modified**: `infra/_framework-pkg/_framework/_git_root/CLAUDE.md` — removed item 4 from Script Placement decision list (`4. Standalone utility (manual only) → infra/_framework-pkg/_scripts/human-only/<name>/`). Root `CLAUDE.md` is a symlink to this file, so both are updated.
- **Modified**: `infra/_framework-pkg/_docs/framework/code-architecture.md` — removed `human-only-scripts/` line from directory tree
- **Modified**: `infra/_framework-pkg/_docs/readme-maintenance/README-tracker.md` — removed stale entry for deleted `_human-only-scripts/gpg/README.gpg-setup.md`
- **Modified**: `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — updated tooltip to say "ai-only utilities" instead of "human-only utilities"

## What was left alone

All `ai-log/` and `ai-plans/archived/` references — these are historical records of past
work and correctly describe what existed at the time they were written.
