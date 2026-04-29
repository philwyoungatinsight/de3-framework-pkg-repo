# Reorganize MaaS docs into maas-pkg/_docs

## Summary

MaaS-specific troubleshooting and background process details were scattered across
framework-level docs (`docs/framework/troubleshooting.md`, `docs/background-jobs.md`).
These are now consolidated in `infra/maas-pkg/_docs/` with links back from the framework
docs, keeping cross-package references as short summaries with pointers.

## Changes

- **`infra/maas-pkg/_docs/troubleshooting.md`** (new) — MaaS-specific troubleshooting:
  `power_state=error` commission blocks, stuck-in-New, tainted resources; replaces the
  two MaaS sections that were in `docs/framework/troubleshooting.md`
- **`docs/framework/troubleshooting.md`** — replaced the two MaaS sections with a single
  stub + link to `infra/maas-pkg/_docs/troubleshooting.md`
- **`docs/background-jobs.md`** — five changes:
  1. MaaS job descriptions (auto-import through wait-for-deployed) replaced with a
     short summary block + link to `infra/maas-pkg/_docs/background-processes.md`
  2. Stale Tier 1 reference removed from GUI local state watcher description
  3. Two new GUI tasks added: `sync_unit_status_from_gcs`, `sync_wave_status_from_gcs`
  4. Quick reference diagram updated to show all 5 GUI background tasks
  5. Full inventory table updated with the two new GCS sync entries
- **`infra/de3-gui-pkg/_docs/background-tasks.md`** — added link to
  `infra/maas-pkg/_docs/background-processes.md` in the Tier 0b section
