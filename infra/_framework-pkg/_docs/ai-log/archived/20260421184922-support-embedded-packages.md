# ai-log: support-embedded-packages

**Date**: 2026-04-21
**Plan**: `infra/_framework-pkg/_docs/ai-plans/support-embedded-packages.md`

## What was done

Added explicit `package_type: embedded | external` field to all entries in
`framework_packages.yaml` and renamed `public` → `exportable` throughout.

### Files changed

- `infra/_framework-pkg/_config/framework_packages.yaml` — added `package_type` to all 13 entries; renamed `public` → `exportable`; updated comment header with schema examples
- `infra/_framework-pkg/_config/framework_manager.yaml` — updated both example `framework_packages` blocks to use `package_type` + `exportable`
- `infra/_framework-pkg/_framework/_pkg-mgr/run`:
  - `_cmd_sync`: added `package_type` validation block (exits on missing/wrong type, external without repo, embedded with repo); switched loop filter and `active_names` from `p.get("repo")` to `package_type == "external"`
  - `_cmd_list_remote`: `p.get("public")` → `p.get("exportable")`
  - `_cmd_import`: new entries get `package_type: "external"`, `exportable: False` instead of `public: False`
  - `_cmd_copy`: fallback entry gets `package_type: "embedded"`, `exportable: False`
  - `_cmd_status`: `imported`/`builtin` lists now built from `package_type`; method column shows `package_type` value directly; footer updated to `external · embedded`
  - `_cmd_clean`: `active_pairs` filter uses `package_type == "external"`
- `infra/_framework-pkg/_framework/_pkg-mgr/README.md` — updated Nomenclature (built-in→embedded, imported→external) and Package schema section (new required fields, examples)
- `infra/_framework-pkg/_framework/_fw-repo-mgr/run` — comment clarification only in `_prune_infra`
- `infra/_framework-pkg/_config/_framework-pkg.yaml` — bumped version `1.4.1` → `1.4.2`

## Verification

- `pkg-mgr --status` shows `external`/`embedded` in Method column; footer `11 external · 2 embedded · 1 clone`
- `pkg-mgr --sync` completes without validation errors
