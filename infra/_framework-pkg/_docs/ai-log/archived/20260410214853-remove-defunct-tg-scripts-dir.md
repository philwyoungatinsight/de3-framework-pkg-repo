# Remove defunct scripts/tg-scripts/ directory

## Summary

`scripts/tg-scripts/` was the old location for Terragrunt hook scripts. All real scripts
have long since been migrated to `infra/<pkg>/_tg_scripts/`. The directory contained only
a stale `.venv` and was never referenced by any live code.

## Changes

- **Deleted** `scripts/tg-scripts/` (contained only `.venv`)
- **Removed** `_setup_tg_venv()` from `infra/default-pkg/_setup/run` — it created the venv
  at the deleted path; no code invoked it after the migration
- **Updated CLAUDE.md** Script Placement section: step 2 now reads
  `infra/<pkg>/_tg_scripts/<role>/<name>/run` (was the defunct `scripts/tg-scripts/default-pkg/...`)
- **Fixed stale comments** in 10 terragrunt.hcl files that still referenced
  `scripts/tg-scripts/default/image-maker/build-images/run` — updated to
  `infra/image-maker-pkg/_tg_scripts/image-maker/build-images/run`
  Files: image-maker VM units (proxmox-pkg examples + pwy-home-lab-pkg),
  test-packer-ubuntu-24-vm, test-packer-rocky-9-vm, test-kairos-ubuntu-24-vm,
  test-kairos-rocky-9-vm (both example and real pkg variants)
- **Fixed** `infra/pwy-home-lab-pkg/_tg_scripts/local/update-ssh-config/run`:
  generated-file header comment now reflects the actual script path
- **Fixed** `sync-maas-api-key` reference in CLAUDE.md Existing Scripts section
