# Fix Remaining Stale config/framework.yaml Paths After Consolidation

**Date**: 2026-04-19
**Session**: fix-remaining-config-framework-paths

## What was done

Fixed remaining stale references to the old `config/framework.yaml` path in six files after the framework config was consolidated into `infra/default-pkg/_config/framework.yaml`.

## Files changed

- `infra/default-pkg/_utilities/bash/gcs-status.sh` — updated path reference to `infra/default-pkg/_config/framework.yaml`
- `infra/default-pkg/_utilities/python/gcs_status.py` — updated path reference to `infra/default-pkg/_config/framework.yaml`; also fixed incorrect `parents[2]` index to `parents[4]` to correctly reach the git root from `infra/default-pkg/_utilities/python/`
- `infra/default-pkg/_scripts/human-only/purge-gcs-status/run` — updated path reference to `infra/default-pkg/_config/framework.yaml`
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/playbook.yaml` — updated path reference
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-sanity/playbook.yaml` — updated path reference
- `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — updated path reference

## Root cause

The framework config was moved/consolidated to `infra/default-pkg/_config/framework.yaml` but these six files still referenced the old `config/framework.yaml` path. Additionally, `gcs_status.py` had an off-by-one error in the `parents[]` index used to compute the git root from its location in the directory tree.

## No rules violated
