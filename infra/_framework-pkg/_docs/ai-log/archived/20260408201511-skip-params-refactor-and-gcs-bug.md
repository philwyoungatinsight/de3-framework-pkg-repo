# 2026-04-08 — Skip params refactor, UniFi destroy bug fix, GCS bucket partial deletion fix

## Summary

Three related issues found and fixed in this session.

---

## Bug: UniFi (and other) units silently excluded from all Terragrunt actions

**Root cause:** `skip: true` was set on `examples/` ancestor config_params paths
to mark them as "config anchors only, not real units". But because `_unit_skip` in
root.hcl read from inherited `unit_params.skip`, ALL child units (network, port-profile,
device, etc.) also inherited `skip: true`. This caused the `exclude { actions = ["all"] }`
block to fire for every unit under `examples/` — meaning terragrunt would never apply
or destroy them.

This was introduced during the default-pkg refactoring when `_unit_skip` logic was added
to root.hcl. The old code had no such check.

**Fix:** Full rename and redesign of skip parameters.

---

## Changes: _skip_FOO parameter system (commit e2f5d19)

### New parameter naming convention

| Parameter | Where | Inherits? | Excludes |
|-----------|-------|-----------|---------|
| `_skip_on_build: true` | `config_params` | Yes | apply, plan, validate, output, state |
| `_skip_on_clean: true` | `config_params` | Yes | destroy |
| `_skip_on_build_without_inheritance: true` | `config_params` | No | apply, plan, validate, output, state |
| `_skip_on_clean_without_inheritance: true` | `config_params` | No | destroy |
| `_skip_on_clean: true` | wave `waves:` block | N/A | wave skipped by `./run --clean` |

**`make clean-all` ignores ALL skip parameters unconditionally.**

### root.hcl changes

Replaced single `exclude { if = _wave_skip || _unit_skip, actions = ["all"] }` with
three targeted blocks:
- Wave skip → all actions
- Build skip → apply/plan/validate/output/state  
- Clean skip → destroy only

### Package config changes

- Replaced `skip: true` → `_skip_on_build: true` at `examples/` ancestor paths in
  all 10 packages (aws, azure, gcp, unifi, proxmox, maas, image-maker, mesh-central,
  null, demo-buckets).
- Removed redundant `skip: true` at regional child paths (us-east-1, eastus,
  us-central1) — these were only needed because the flag wasn't inherited before.
- Renamed wave `skip_on_clean` → `_skip_on_clean` in unifi-pkg, maas-pkg, gcp-pkg.

### New doc: docs/framework/skip-parameters.md

Describes all four unit-level skip parameters, the wave-level `_skip_on_clean`,
inheritance behavior, and clean-all bypass.

---

## Bug: GCS bucket partial deletion in make clean-all

**Symptom:** One specific GCS object consistently survived `stage_wipe_remote_state`
three times in a row. No error was printed.

**Root cause:** `gsutil -m rm -I` return code was never checked. A partial failure
(one object failing to delete) would cause the process to exit non-zero, but the
code called `p.communicate()` without checking `p.returncode`.

**Fix (commit e2f5d19):** 
- Capture stderr and check `p.returncode` after `gsutil -m rm`.
- Add a verification pass: after bulk delete, re-run `gsutil ls -r` to find survivors.
- Retry each survivor individually with `gsutil rm <obj>` and print success/failure.
- The next `make clean-all` run will reveal which specific object always survives
  and why it fails.
