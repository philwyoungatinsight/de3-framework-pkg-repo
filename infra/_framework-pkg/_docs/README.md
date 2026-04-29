# de3 – docs

A Terragrunt implicit-stack for a hybrid multi-cloud home lab.
Entry point: `root.hcl`. Units live under `infra/`. Run via `make` or `./run`.

## Setup

```bash
make setup   # installs all CLI tools and language dependencies (idempotent)
make seed    # provision cloud accounts and authenticate (idempotent)
make         # apply all waves
```

`make setup` runs `./run --setup-packages`, which executes `infra/<pkg>/_setup/run`
for every package — `_framework-pkg` first, then all others alphabetically. Each script
is idempotent and branches on the detected platform (Homebrew / apt / dnf).
See the root `README.md` for the full tool list.

`make seed` runs `./run --seed-packages`, which executes `infra/<pkg>/_setup/seed`
for every package that has one — running login → seed → test in sequence. The login
step verifies existing credentials and only opens a browser OAuth flow if needed.

## Package Docs

| Package | README | What it covers |
|---------|--------|----------------|
| `maas-pkg` | [maas-pkg/_docs/README.md](../../maas-pkg/_docs/README.md) | MaaS automation: commissioning flow, power drivers, AMT SSL fix, smart-plug proxy |
| `maas-pkg` | [maas-pkg/_docs/machine-onboarding.md](../../maas-pkg/_docs/machine-onboarding.md) | Physical setup, cabling, BIOS/MEBx, YAML config for adding bare-metal PXE hosts |
| `proxmox-pkg` | [proxmox-pkg/_docs/README.md](../../proxmox-pkg/_docs/README.md) | Setting up Proxmox hosts deployed by MaaS |
| `image-maker-pkg` | [image-maker-pkg/_docs/README.md](../../image-maker-pkg/_docs/README.md) | ISOs, cloud images, Packer builds, Kairos ISOs, MaaS boot images |
| `unifi-pkg` | [unifi-pkg/_docs/README.md](../../unifi-pkg/_docs/README.md) | VLAN table, subnet purposes, UniFi switch layout |
| `mikrotik-pkg` | [mikrotik-pkg/_docs/README.md](../../mikrotik-pkg/_docs/README.md) | MikroTik CRS317 10GigE switch managed via routeros Terraform provider |
| `de3-gui-pkg` | [de3-gui-pkg/_docs/README.md](../../de3-gui-pkg/_docs/README.md) | GUI package for visualising and operating the infrastructure DAG |

## Framework Docs

| File | What it covers |
|------|----------------|
| [framework/code-architecture.md](framework/code-architecture.md) | Execution pipeline, config resolution, wave system, dependency model |
| [framework/config-files.md](framework/config-files.md) | Config file layout, deep-merge mechanism, package system, adding a new package |
| [framework/framework-repo-manager.md](framework/framework-repo-manager.md) | `fw-repo-mgr`: creating repos, `local_only` validation workflow, per-repo field reference |
| [framework/package-system.md](framework/package-system.md) | Package system: what a package owns, current packages, `p_package` routing |
| [framework/waves.md](framework/waves.md) | Wave system: YAML config, `TG_WAVE` filter, per-wave steps, reverse destroy |
| [framework/unit_params.md](framework/unit_params.md) | Reserved keys in `unit_params`; ancestor-path merge rules |
| [framework/skip-parameters.md](framework/skip-parameters.md) | `_skip_on_build` (unit, inherited); wave-level `_skip_on_wave_run`; `make clean-all` bypass |
| [framework/gui-build-status.md](framework/gui-build-status.md) | How the GUI tracks and displays per-unit build status |
| [framework/troubleshooting.md](framework/troubleshooting.md) | Tainted resources, stale locks, YAML parse errors, AMT failures, Proxmox auth |

## Reference

| File | What it covers |
|------|----------------|
| [known-pitfalls.md](known-pitfalls.md) | Known failure modes and their fixes |
| [idempotence-and-tech-debt.md](idempotence-and-tech-debt.md) | `make clean-all && make` invariant; known manual steps and automation gaps |
| [claude-skills.md](claude-skills.md) | Claude Code slash commands (`/run-wave`): algorithm, fix rules, test failure policy |

## AI Logs

| Location | What it contains |
|----------|-----------------|
| [ai-log/](ai-log/) | Timestamped session logs — one file per significant change |
| [ai-log-summary/README.ai-log-summary.md](ai-log-summary/README.ai-log-summary.md) | Compacted current-state summary of all ai-logs |
