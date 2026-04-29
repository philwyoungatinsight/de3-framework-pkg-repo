# Cleanup: remove cat-hmc legacy paths and standardise _docs/ structure

**Date:** 2026-04-10
**Commits:** 868662c, 0285ec8

## Summary

Two independent cleanups: removal of the legacy `cat-hmc`/`cat-N` catalog
prefix from all documentation and code, and standardisation of per-package
documentation under a `_docs/` directory.

---

## 1. Remove cat-hmc / cat-N legacy path prefixes

### Background

The project originally used a "catalog" prefix system to namespace
infrastructure paths:
- `cat-hmc` — on-premises / home-lab
- `cat-1`, `cat-2` — GCP cloud resources
- `cat-3` — AWS cloud resources

These were replaced by the package-scoped path format (`<pkg>/_stack/<provider>/...`)
during the migration to the self-contained package system. All active config and
state was migrated, but ~150 references remained in documentation, comments,
and GUI mock data.

### Changes (commit 868662c)

20 files updated. Key replacement map:

| Old | New |
|-----|-----|
| `cat-hmc/maas/example-lab/` | `maas-pkg/_stack/maas/examples/example-lab/` |
| `cat-hmc/maas/pwy-homelab/` | `pwy-home-lab-pkg/_stack/maas/pwy-homelab/` |
| `cat-hmc/proxmox/example-lab/` | `proxmox-pkg/_stack/proxmox/examples/example-lab/` |
| `cat-hmc/proxmox/pwy-homelab/` | `proxmox-pkg/_stack/proxmox/pwy-homelab/` |
| `cat-hmc/null/example-lab/maas/` | `maas-pkg/_stack/null/examples/example-lab/maas/` |
| `cat-hmc/null/pwy-homelab/mesh-central/` | `pwy-home-lab-pkg/_stack/null/pwy-homelab/mesh-central/` |
| `cat-hmc/unifi/pwy-homelab` | `unifi-pkg/_stack/unifi/pwy-homelab` |
| `cat-1/gcp/` | `gcp-pkg/_stack/gcp/` |
| `cat-3/aws/` | `aws-pkg/_stack/aws/` |

Also corrected stale GCS bucket name `tf-state-ai-garden-terragrunt-lab-stack`
→ `seed-tf-state-pwy-homelab-20260308-1700` in troubleshooting.md.

`homelab_gui.py` mock data (`_SYNTHETIC_COMPOUND_ELEMENTS` and
`_SYNTHETIC_RF_SOURCE`) fully updated with correct node IDs and parent
references matching the current path format.

---

## 2. Standardise package docs under _docs/

### Decision

Every package stores documentation in `infra/<pkg>/_docs/`. No `README.md`
at the package root. Consistent with the `_`-prefix convention used for all
other package directories (`_stack`, `_modules`, `_config`, etc.).

### Changes (commit 0285ec8)

- `git mv` `docs/` → `_docs/` in four packages: image-maker, maas, proxmox, unifi
- Moved `infra/de3-gui-pkg/README.md` → `infra/de3-gui-pkg/_docs/README.md`
- Created `infra/<pkg>/_docs/.gitkeep` for seven packages with no existing
  docs (aws, azure, default, demo-buckets-example, gcp, mesh-central, pwy-home-lab)
- Fixed all cross-references: CLAUDE.md, docs/README.md (links were previously
  broken, now pointing to correct `../infra/<pkg>/_docs/` paths),
  troubleshooting.md, proxmox-pkg/_docs/README.md
- Added `_docs/` convention rule to CLAUDE.md

---

## 3. maas-pkg.yaml examples: AMT reference comments for ms01-02/ms01-03

Added commented-out AMT hardware reference blocks for ms01-02 and ms01-03
in the examples config, matching the existing ms01-01 block. Includes static
IP and idle timeout reminder. `mac: ?` is a placeholder — user to fill in
after verifying MEBx setup.
