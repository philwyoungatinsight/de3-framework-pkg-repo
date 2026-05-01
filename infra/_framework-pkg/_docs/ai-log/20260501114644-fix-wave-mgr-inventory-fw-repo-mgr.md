# Fix: pre-apply GCS unlock, generate-inventory config path, fw-repo-mgr .gitlab-ci.yml

## Summary

Three bugs discovered and fixed while running `./run -n 1` in pwy-home-lab-pkg. The pre-apply
GCS state unlock was silently skipping every wave because package-level `config_params` were
never scanned for `_wave` keys. `generate_ansible_inventory.py` had a stale hard-coded path
that missed both the `_framework_settings/` reorganization and the main package tier entirely.
`fw-repo-mgr` was leaving a dangling `.gitlab-ci.yml` symlink in every generated repo after
pruning `default-pkg`.

## Changes

- **`infra/_framework-pkg/_framework/_wave-mgr/wave-mgr`** — `get_wave_unit_prefixes` now
  scans `cfg['config_params']` (package-level) in addition to `cfg['providers'][*]['config_params']`.
  Package-level `config_params` is now merged into `cfg` at load time so the unlock correctly
  finds all wave units and clears their GCS locks before each apply attempt.

- **`infra/_framework-pkg/_framework/_generate-inventory/generate_ansible_inventory.py`** —
  `resolve_config_path` replaced with a call to `find_framework_config_dirs` (imported from
  `_utilities/python/framework_config.py`). `load_stack_config` now delegates to
  `load_framework_config` when given a list of dirs. All three config tiers are now loaded:
  framework defaults → main package overrides → `config/` ad-hoc.

- **`infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr`** — after `prune_infra()`,
  removes `.gitlab-ci.yml` if it is a dangling symlink. `default-pkg` is always pruned so
  the symlink to `infra/default-pkg/_framework/_git_root/.gitlab-ci.yml` always dangled.

- **`infra/_framework-pkg/_framework/_fw-repo-mgr/README.md`** — step 2 updated to document
  the `.gitlab-ci.yml` cleanup.

## Root Cause

**Wave-mgr unlock**: `pwy-home-lab-pkg.yaml` puts `config_params` at the top level of the
package config (not inside a `providers` wrapper). `get_wave_unit_prefixes` only iterated
`providers[*].config_params`, so it always returned an empty prefix list and
`unlock_wave_locks` returned immediately without doing anything.

**generate-inventory**: the function hard-coded `infra/_framework-pkg/_config/` and globbed
directly for `framework_*.yaml`. After the `_framework_settings/` reorganization those files
moved to `_config/_framework_settings/`. The main package tier (`$_FRAMEWORK_MAIN_PACKAGE_DIR`)
was never checked at all.

**fw-repo-mgr .gitlab-ci.yml**: `rsync` copies `.gitlab-ci.yml` from the source repo, but
then `prune_infra()` removes `infra/default-pkg/` (its target), leaving the symlink dangling
on every build. No post-prune cleanup existed.

## Notes

- `generate_ansible_inventory.py` did not previously import from `_utilities/python/` —
  `sys.path.insert(0, parents[1] / "_utilities" / "python")` added alongside the import.
- The `.gitlab-ci.yml` fix in all 13 existing generated repos was applied separately via a
  one-off loop (`git rm .gitlab-ci.yml` + commit in each repo) before the fw-repo-mgr fix.
