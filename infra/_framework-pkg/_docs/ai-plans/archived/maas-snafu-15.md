# Plan: maas-snafu-15 — AMT TLS Fix + IP Conflict on Deploy + nuc-1 Removal

## Objective

Three related fixes discovered while deploying ms01-01/02/03:
1. AMT wsman SSL failures due to OpenSSL 3.0+ blocking legacy TLS renegotiation
2. MaaS deploy rejecting machines whose old OS still holds the provisioning IP (ARP conflict)
3. Remove nuc-1 from all config and unit trees (machine permanently abandoned)

## What Broke

### AMT "Error determining BMC task queue" (UnroutablePowerWorkflowException)

Root cause chain:
1. **PRIMARY**: Management subnet `10.0.11.0/24` (containing AMT BMC IPs at `10.0.11.x`) was absent from MaaS's known subnets. MaaS Temporal power workflow's `filter_by_url_accessible` could find no rack controller for the BMC IP → `UnroutablePowerWorkflowException`.
   - Fixed by adding `management` to `managed_networks` in `pwy-home-lab-pkg.yaml` and running the ad-hoc OpenSSL script to add it live.
2. **SECONDARY**: OpenSSL 3.0+ disables legacy TLS renegotiation. Intel AMT firmware requires it. `wsman` (run by rackd/maas-agent on the rack controller) was failing with `SSL connect error`.
   - Root cause: `fix-maas-amt-ssl.yaml` was only included in the region server playbook, NOT the rack controller playbook. Even when included on the region, pebble does NOT propagate env vars to managed child services.
   - Fix: patch `/etc/ssl/openssl.cnf` directly on BOTH region AND rack. System-wide file is read by all processes using system libssl.so.3 regardless of env vars.

### Deploy rejected: "reserved ip X.X.X.X in use"

ms01-02 had its previous deployed OS still running, holding `10.0.12.239` (its fixed provisioning IP). MaaS ARP-checks provisioning IPs before deploying. The ARP check found the IP occupied and refused.

Fix: `trigger-deploy.sh` now queries BMC power state before the deploy call. If machine is ON, it powers it off and waits 15s before issuing the deploy command.

### nuc-1 permanently abandoned

Machine never commissioning reliably (smart_plug only, no AMT, BIOS boots to disk not PXE). User gave up. Deleted from MaaS, GCS state wiped, all unit files removed.

## Files Changed

### `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/fix-maas-amt-ssl.yaml` — modified
- Rewrote to use two-layer fix:
  - **Layer 1 (PRIMARY)**: Patch `/etc/ssl/openssl.cnf` directly (Python) to add `ssl_conf = ssl_sect` + `UnsafeLegacyRenegotiation` — picked up by ALL processes using system OpenSSL
  - **Layer 2**: Keep systemd drop-in for pebble service as belt-and-suspenders
- MaaS API wait now conditional (`when: _maas_url is defined and _maas_url != ''`) — skips wait on rack controller which has no local API
- Restart command changed to `snap restart maas` (full restart)

### `infra/maas-pkg/_tg_scripts/maas/configure-rack/playbook.configure-rack.yaml` — modified
- Added `fix-maas-amt-ssl.yaml` include after rack installation
- Rack controller spawns wsman for AMT operations — this was the missing piece

### `infra/maas-pkg/_modules/maas_lifecycle_deploy/scripts/trigger-deploy.sh` — modified
- Step 3 rewritten: query actual BMC power state first
  - If ON: power off, wait 15s (releases provisioning IP for MaaS ARP check)
  - If OFF: power on for PXE target (original behavior)

### `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml` — modified
- Added `management` subnet to `managed_networks` (10.0.11.0/24, dhcp_enabled: false)
- Removed nuc-1 machine entry (lines 225-243)
- Removed all 6 nuc-1 lifecycle unit entries
- Removed `nuc-1` from `machine_paths` in `configure-physical-machines`
- Cleared UniFi switch port 12 (was `nuc-1` with MAC + port profile)

### `infra/pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/nuc-1/` — deleted
- Entire unit tree (7 files): terragrunt.hcl + 5 lifecycle stage HCLs + lock files

### `scripts/ai-only-scripts/fix-maas-openssl-legacy-renegotiation/` — new
- Ad-hoc script to apply the openssl.cnf patch on live servers (10.0.10.11 + 10.0.10.13)
- Used for immediate fix; permanent fix is in configure-server and configure-rack playbooks

## Verification

After next full rebuild:
1. AMT power operations should succeed without SSL errors on both region and rack
2. Deploy should succeed even when machine has its old OS running
3. nuc-1 should not appear in MaaS, TF state, or wave logs

## Status: COMPLETE
