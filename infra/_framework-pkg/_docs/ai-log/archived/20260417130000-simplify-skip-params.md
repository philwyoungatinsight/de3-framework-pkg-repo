# Simplify Skip Parameters: Remove Dead _skip_on_build_without_inheritance

## Summary

Removed the dead `_skip_on_build_without_inheritance` parameter and its
`_skip_on_build_exact` local from `root.hcl`. It was never used in any
`config_params` YAML. This leaves exactly two skip features: wave-level
`_skip_on_wave_run` and unit-level `_skip_on_build`. Also removed the
misleading "Terragrunt only allows one exclude block" complaint — `root.hcl`
already ORs multiple conditions into one block; that was never a constraint.

## Changes

- **`root.hcl`** — removed `_skip_on_build_exact` local and the `_skip_on_build_without_inheritance` read; updated comment block; simplified exclude condition to `_wave_skip || _skip_on_build`
- **`docs/framework/skip-parameters.md`** — removed "Non-inherited parameters" subsection, the `_skip_on_build_without_inheritance` table row, and the misleading "unit-level _skip_on_wave_run not supported" note; updated summary table to two rows
- **`docs/framework/unit_params.md`** — removed `_skip_on_build_without_inheritance` section entirely
- **`CLAUDE.md`** — removed `_skip_on_build_without_inheritance` from `_skip_FOO` params bullet; removed "one exclude block" complaint

## Notes

The "one exclude block" wording was factually wrong: Terragrunt allows multiple
conditions ORd together in one block. The real limitation is that `actions` must
be a static list (can't conditionally apply/skip only apply vs only destroy per
condition). That distinction was never relevant to the skip features here.
