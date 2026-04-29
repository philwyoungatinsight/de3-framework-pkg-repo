---
date: 2026-04-09
title: Distribute clean-all pre-purge stages into per-package _clean_all/run scripts
---

## What changed

Replaced the three hardcoded pre-Terraform purge stages in
`framework/clean-all/run` (Proxmox VM deletion, UniFi VLAN/port-profile
deletion, GKE cluster deletion) with a generic discovery loop (Stage 0) that
runs `infra/<pkg>/_clean_all/run` for each package listed under
`clean_all.pre_destroy_order` in `config/framework.yaml`.

## New files

- `infra/proxmox-pkg/_clean_all/run` — extracted Proxmox REST API VM purge
- `infra/gcp-pkg/_clean_all/run` — extracted GKE gcloud cluster purge
- `infra/unifi-pkg/_clean_all/run` — extracted UniFi VLAN/port-profile purge

## Data passing

The framework loads all config params and decrypts all SOPS secrets once, then
passes them to each package script as JSON in two environment variables:
  - `_CLEAN_ALL_CONFIG_PARAMS` — public config (all_config_params)
  - `_CLEAN_ALL_SECRET_PARAMS` — decrypted secrets (all_secret_params)

This avoids repeated SOPS decryption across package scripts.

## Adding future packages

To add a new package that needs pre-Terraform cleanup:
1. Create `infra/<pkg>/_clean_all/run` (reads the two JSON env vars above)
2. Add `<pkg>` to `clean_all.pre_destroy_order` in `config/framework.yaml`
   (insert before packages that depend on resources this package creates)

## Why this ordering (proxmox-pkg → gcp-pkg → unifi-pkg)

Compute/VMs before networking — reverse of build order. Proxmox VMs sit on top
of UniFi networks; deleting them first avoids leaving orphaned NICs when
networks disappear. GKE clusters are cloud resources independent of the others.
