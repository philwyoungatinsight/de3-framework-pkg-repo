# Fix package filter to use infra path instead of module package

## What changed

Fixed the folder-view package filter so it correctly filters by the infrastructure package
(first segment of the node's `path`, e.g. `maas-pkg`) instead of `node["package"]` (which
is the MODULE source package and points to the wrong package for cross-package module
consumers).

## Root cause

`node["package"]` is populated by `_populate_module_tree_paths` from the module registry —
it reflects where the Terraform *module* lives, not where the unit lives under `infra/`.
Units in `pwy-home-lab-pkg/_stack/maas/...` use modules from `maas-pkg`, so they were
classified as `maas-pkg` by the filter even though they live under `pwy-home-lab-pkg`.
This caused `pwy-home-lab-pkg` to appear when filtering to `maas-pkg`, and nothing to
appear when filtering to `pwy-home-lab-pkg`.

The correct infra package is always `node["path"].split("/")[0]`.

## Files modified

- `infra/de3-gui-pkg/_applications/de3-gui/homelab_gui/homelab_gui.py`

## Locations changed (6 total)

1. `packages_with_visibility` — dict comprehension iterating `all_nodes`
2. `_pkg_match` closure inside `visible_nodes` — used to build `package_keep`
3. `_m_pkg_match` closure inside `merged_visible_nodes` — used to build `package_keep_m`
4. `package_filters` init in `on_load` — initial filter state on startup
5. `package_filters` re-init in `refresh_infra_data` (two occurrences — both updated)
