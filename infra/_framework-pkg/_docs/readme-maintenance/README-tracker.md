# README Maintenance Tracker

Tracks all README files in the repo. Process them in priority order using `/doit` against this file.
Update the **Status** and **Last Reviewed** columns after each README is verified or updated.

**Status legend:**
- `pending` — not yet reviewed
- `updated` — reviewed and updated this cycle
- `ok` — reviewed, no changes needed
- `skip` — intentionally not maintained (auto-generated, archived, etc.)

---

## Priority 1 — Core / Entry-Point READMEs

Most visible; read by anyone onboarding or running the stack.

| # | File | Description | Last Git Commit | Last Reviewed | Status |
|---|------|-------------|-----------------|---------------|--------|
| 1 | `README.md` | Root repo overview: Terragrunt implicit-stack, 13 packages, `./run` lifecycle | 2026-04-19 | 2026-04-20 | ok |
| 2 | `infra/_framework-pkg/_docs/README.md` | de3 docs index: entry point, `root.hcl`, units under `infra/` | 2026-04-19 | 2026-04-20 | updated |
| 3 | `infra/_framework-pkg/_framework/README.md` | Framework tools overview: `_ephemeral`, `_generate-inventory`, `_unit-mgr`, `_pkg-mgr`, `_clean_all`, `_utilities` | 2026-04-19 | 2026-04-20 | ok |

---

## Priority 2 — Package Documentation READMEs

One per package; describes what the package does and how it fits in the build.

| # | File | Description | Last Git Commit | Last Reviewed | Status |
|---|------|-------------|-----------------|---------------|--------|
| 4 | `infra/maas-pkg/_docs/README.md` | MaaS automation guide: Proxmox VM → MaaS server → physical machine full lifecycle | 2026-04-19 | 2026-04-20 | updated |
| 5 | `infra/proxmox-pkg/_docs/README.md` | MaaS-provisioned Proxmox host setup: physical machine → PVE server | 2026-04-19 | 2026-04-26 | updated |
| 6 | `infra/unifi-pkg/_docs/README.md` | Network plan: VLANs, subnets, UniFi switch configuration | 2026-04-19 | 2026-04-26 | updated |
| 7 | `infra/image-maker-pkg/_docs/README.md` | ISOs, images, Packer builds: image-maker VM, idempotent pipeline | 2026-04-19 | 2026-04-29 | updated |
| 8 | `infra/de3-gui-pkg/_docs/README.md` | de3-gui-pkg: optional GUI for visualising and operating the infra DAG | 2026-04-19 | 2026-04-29 | updated |
| 9 | `infra/mikrotik-pkg/_docs/README.md` | MikroTik CRS317 10GigE switch managed via routeros Terraform provider | 2026-04-19 | 2026-04-29 | updated |
| 10 | `infra/mesh-central-pkg/_tg_scripts/mesh-central/README.md` | tg-scripts index for MeshCentral remote-management server | 2026-04-19 | 2026-04-29 | ok |

---

## Priority 3 — Script / tg-script READMEs

Documents individual automation scripts invoked by Terragrunt or waves.

| # | File | Description | Last Git Commit | Last Reviewed | Status |
|---|------|-------------|-----------------|---------------|--------|
| 11 | `infra/maas-pkg/_tg_scripts/maas/README.md` | tg-scripts index: MaaS server setup and physical machine lifecycle | 2026-04-19 | 2026-04-29 | updated |
| 12 | `infra/maas-pkg/_tg_scripts/maas/configure-region/README.md` | configure-region: Ansible installs/configures MaaS server, verifies health | 2026-04-19 | 2026-04-29 | updated |
| 13 | `infra/maas-pkg/_tg_scripts/maas/configure-server/README.md` | configure-server: same as configure-region — check if duplicate | 2026-04-19 | 2026-04-29 | updated |
| 14 | `infra/maas-pkg/_tg_scripts/maas/configure-region/README.why-ansible.md` | Why Ansible instead of MaaS Terraform provider for subnets/VLANs | 2026-04-19 | 2026-04-29 | ok |
| 15 | `infra/maas-pkg/_tg_scripts/maas/configure-server/README.why-ansible.md` | Same rationale doc in configure-server — check if duplicate | 2026-04-19 | 2026-04-29 | ok |
| 16 | `infra/maas-pkg/_tg_scripts/maas/configure-machines/README.md` | configure-physical-machines: registers Intel AMT power drivers in MaaS | 2026-04-19 | 2026-04-29 | updated |
| 17 | `infra/proxmox-pkg/_tg_scripts/proxmox/README.md` | tg-scripts index: PVE install, configure, readiness scripts with wave column | 2026-04-19 | 2026-04-29 | ok |
| 18 | `infra/proxmox-pkg/_tg_scripts/proxmox/install/README.md` | install-proxmox: installs PVE 9 on Debian 13 (trixie) bare-metal hosts | 2026-04-19 | 2026-04-29 | updated |
| 19 | `infra/proxmox-pkg/_tg_scripts/proxmox/configure/README.md` | proxmox/configure: storage content types, TF API token, Linux bridges, VLANs | 2026-04-19 | 2026-04-29 | updated |
| 20 | `infra/image-maker-pkg/_tg_scripts/image-maker/README.md` | tg-scripts index: Packer build scripts run on image-maker VM | 2026-04-19 | 2026-04-29 | ok |
| 21 | `infra/image-maker-pkg/_tg_scripts/image-maker/build-images/README.md` | build-images: builds Proxmox VM templates and Kairos ISOs | 2026-04-19 | — | pending |
| 22 | `infra/mesh-central-pkg/_tg_scripts/mesh-central/install/README.md` | install-mesh-central: installs MeshCentral on dedicated VM | 2026-04-19 | — | pending |
| 23 | `infra/mesh-central-pkg/_tg_scripts/mesh-central/update/README.md` | update-mesh-central: enrolls hosts into MeshCentral, configures Intel AMT | 2026-04-19 | — | pending |
| 24 | `infra/gcp-pkg/_tg_scripts/gke/kubeconfig/README.md` | gke/kubeconfig: fetches kubectl credentials, writes per-cluster kubeconfig | 2026-04-19 | — | pending |

---

## Priority 4 — Wave Script READMEs

Documents wave-level test and validation playbooks.

| # | File | Description | Last Git Commit | Last Reviewed | Status |
|---|------|-------------|-----------------|---------------|--------|
| 25 | `infra/unifi-pkg/_wave_scripts/common/verify-unifi-networking/README.md` | verify-unifi-networking: validates live UniFi switch vs YAML config | 2026-04-19 | — | pending |
| 26 | `infra/unifi-pkg/_wave_scripts/test-ansible-playbooks/network/network-validate-config/README.md` | network-validate-config: wave test playbook for network.unifi.validate-config | 2026-04-19 | — | pending |

---

## Priority 5 — Framework Internals

Describes tools used by the build framework itself.

| # | File | Description | Last Git Commit | Last Reviewed | Status |
|---|------|-------------|-----------------|---------------|--------|
| 27 | `infra/_framework-pkg/_framework/_generate-inventory/README.md` | generate-ansible-inventory: reads TF remote state + YAML to produce hosts.yml | 2026-04-19 | — | pending |
| 28 | `infra/_framework-pkg/_framework/_pkg-mgr/README.md` | pkg-mgr: remote package manager, built-in vs remote package distinction | 2026-04-19 | — | pending |
| 29 | `infra/_framework-pkg/_framework/_unit-mgr/README.md` | unit-mgr: Python CLI for moving/copying/renaming Terragrunt units | 2026-04-19 | — | pending |
| 30 | `infra/_framework-pkg/_framework/_ephemeral/README.md` | ephemeral: RAM-drive mount utility (`ephemeral.sh`) | 2026-04-19 | — | pending |
| 31 | `infra/_framework-pkg/_framework/_ai-only-scripts/README.md` | ai-only-scripts: AI-generated diagnostic/recovery scripts, run manually | 2026-04-19 | — | pending |
| 32 | `infra/_framework-pkg/_framework/_utilities/ansible/roles/config_base/README.md` | config_base Ansible role: loads SOPS + non-SOPS YAML config vars | 2026-04-19 | — | pending |
| 33 | `infra/_framework-pkg/_framework/_git_root/README.md` | Git root marker directory README — likely duplicate of root README.md | 2026-04-19 | — | pending |

---

## Priority 6 — GUI / Application READMEs

| # | File | Description | Last Git Commit | Last Reviewed | Status |
|---|------|-------------|-----------------|---------------|--------|
| 34 | `infra/de3-gui-pkg/_application/de3-gui/README.md` | Home Lab GUI: Python Reflex web app, infra tree visualisation, wave tooling | 2026-04-19 | — | pending |
| 35 | `infra/de3-gui-pkg/_application/de3-gui/README.instructions.md` | GUI design instructions: authoritative reference for AI sessions on homelab_gui | 2026-04-19 | — | pending |

---

## Priority 7 — Meta / Logging / Admin READMEs

These describe logging conventions and tooling, not code. Low churn expected.

| # | File | Description | Last Git Commit | Last Reviewed | Status |
|---|------|-------------|-----------------|---------------|--------|
| 36 | `infra/_framework-pkg/_docs/ai-screw-ups/README.md` | AI screw-ups log: records significant Claude mistakes, feeds CLAUDE.md rules | 2026-04-19 | — | pending |
| 37 | `infra/_framework-pkg/_docs/ai-plans/README.md` | ai-plans directory purpose: planning skill, plan → review → execute flow | 2026-04-19 | — | pending |
| 38 | `infra/_framework-pkg/_docs/ai-log/README.ai-log.md` | ai-log convention: per-session log files, summary kept separately | 2026-04-19 | — | pending |
| 39 | `infra/_framework-pkg/_docs/ai-log-summary/README.ai-log-summary.md` | ai-log-summary: compacted current-state facts after individual logs deleted | 2026-04-19 | — | pending |
| 40 | `infra/_framework-pkg/_docs/claude-md-history/README.md` | claude-md-history: tracks CLAUDE.md evolution — do not use for code gen | 2026-04-19 | — | pending |
| 41 | `infra/de3-gui-pkg/_application/de3-gui/docs/ai-log/README.ai-log.md` | GUI ai-log: same convention as root ai-log, scoped to de3-gui | 2026-04-19 | — | pending |
| 42 | `infra/de3-gui-pkg/_application/de3-gui/docs/ai-log-summary/README.ai-log-summary.md` | GUI ai-log-summary: compacted current-state facts for de3-gui | 2026-04-19 | — | pending |

---

## Priority 8 — Archived / Low-Value

Review last; may be candidates for deletion.

| # | File | Description | Last Git Commit | Last Reviewed | Status |
|---|------|-------------|-----------------|---------------|--------|
| 44 | `infra/_framework-pkg/_framework/_ai-only-scripts/archived/README.md` | Archived ai-only scripts: held pending confirmation they are no longer needed | 2026-04-19 | — | pending |
| 45 | `infra/_framework-pkg/_framework/_ai-only-scripts/archived/build-watchdog/README.md` | build-watchdog archive: used by /watchdog skill (CronJob) — may be obsolete | 2026-04-19 | — | pending |

---

## How to Use This File

Use the `/readme-review` skill to process READMEs one at a time. It picks the next `pending` row,
reviews and updates the README if stale, marks it `ok` or `updated`, and commits the change.
Run `/readme-review` repeatedly (or in a `/loop`) until all rows are reviewed.

Manual workflow (if not using the skill):

1. Pick the next `pending` row (work top-to-bottom within each priority group).
2. Read the current file content and the surrounding code/scripts.
3. Update the README if it is stale, wrong, or missing key information.
4. Change **Status** to `updated` or `ok` and set **Last Reviewed** to today's date (`YYYY-MM-DD`).
5. Commit the README change (and this tracker update) together.
6. Run `/clear` and start the next session.
