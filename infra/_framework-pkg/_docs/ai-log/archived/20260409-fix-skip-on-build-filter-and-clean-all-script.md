# Fix _skip_on_build filter in capture-config-fact.yaml; add maas-machine-clean-all script

**Date:** 2026-04-09
**Files modified:**
- `infra/maas-pkg/_config/maas-pkg.yaml`
- `infra/maas-pkg/_tg_scripts/maas/configure-machines/tasks/capture-config-fact.yaml`
- `infra/maas-pkg/_tg_scripts/maas/configure-machines/tasks/wipe-host-clean.yaml`
- `scripts/ai-only-scripts/maas-machine-clean-all/run` (new)
- `scripts/ai-only-scripts/maas-machine-clean-all/playbook.yaml` (new)

## Fix 1: Wrong configure-physical-machines selected (ROOT CAUSE of wave 10 failure)

**Symptom:** Wave 10 (`pxe.maas.machine-entries`) failed with:
```
object of type 'dict' has no attribute 'pxe_mac_address'
```
at `power-on-machine.yaml:24`. Machine dicts had `name` but no `pxe_mac_address`.

**Root cause (two-part):**

`capture-config-fact.yaml` discovers the active `configure-physical-machines` unit by
iterating `_tg_providers['null']['config_params']` keys and filtering by `_skip_on_build`.
There are two `configure-physical-machines` units:
1. `maas-pkg/_stack/null/examples/pwy-homelab/configure-physical-machines` — examples (skipped via `_skip_on_build: true` on ancestor `maas-pkg/_stack/null/examples`)
2. `pwy-home-lab-pkg/_stack/null/pwy-homelab/configure-physical-machines` — the real one

The filter:
```jinja2
{%- if not (merged._skip_on_build | default(false)) -%}
```

Used dot notation on a plain Python dict returned by the `ancestor_merge` filter plugin.
In Ansible's Jinja2 environment, dot notation on `_`-prefixed keys can silently fail
(attribute access returns Undefined, and `| default(false)` converts it to `false`),
so `not false = True` and the examples path was NOT excluded. Both paths passed the
filter; since maas-pkg.yaml loads before pwy-home-lab-pkg.yaml alphabetically, the
examples path came first and was selected by `| first`.

The examples `machine_paths` listed `maas-pkg/_stack/maas/pwy-homelab/machines/...`
(non-existent paths), so `_tg_providers.maas.config_params[item]` returned `{}`
and the machine dicts had no `pxe_mac_address`.

**Fix:** Changed both `_skip_on_build` checks in `capture-config-fact.yaml` from
dot notation to the explicit `.get()` method call:
```jinja2
{%- if not (merged.get('_skip_on_build', false)) -%}
```
`.get()` is a Python dict method — always works regardless of key name prefix.

Also fixed the examples `machine_paths` in `maas-pkg.yaml` to reference the correct
example machine paths (`maas-pkg/_stack/maas/examples/pwy-homelab/machines/...`
instead of the non-existent `maas-pkg/_stack/maas/pwy-homelab/machines/...`).

## Fix 2: Hardcoded examples path in wipe-host-clean.yaml

The debug message in `wipe-host-clean.yaml` after a successful wipe referenced a
hardcoded `maas-pkg/_stack/maas/examples/pwy-homelab/machines/...` path. Changed
to use `machine.path` (a dynamic field already present in the machine config dict).

## New: maas-machine-clean-all script

Created `scripts/ai-only-scripts/maas-machine-clean-all/` for a full reset of MaaS
machine state without rebuilding the MaaS server. Useful when:
- Machines are stuck in a bad MaaS state and need to be re-enlisted from scratch
- Terraform state is inconsistent with MaaS reality
- Testing the full commissioning flow repeatedly

**What it does:**
1. Powers off each machine via smart plug (or AMT for `power_type: amt`)
2. Deletes each machine from MaaS (forces `status=4` via DB first)
3. Removes Terraform state for all machine units:
   - `maas_machine.this`, `maas_instance.this`, `null_resource.commission`,
     `null_resource.pre_deploy_kick`, `null_resource.release_with_erase`,
     `null_resource.set_deploy_osystem[*]`
4. Removes `null_resource.this` from configure-physical-machines unit

**Options:**
- `--extra-vars "skip_power_off=true"` — skip power-off (machines already off)
- `--extra-vars "dry_run=true"` — show what would be done without making changes

**After running:** power machines on (or wait for wave to do it), then:
```bash
./run --apply --start-at 9
```
