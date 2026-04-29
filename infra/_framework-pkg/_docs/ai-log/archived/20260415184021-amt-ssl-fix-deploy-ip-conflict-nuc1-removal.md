# AMT SSL Fix, Deploy IP Conflict Fix, nuc-1 Removal

## Summary

Three interrelated fixes while deploying ms01-01/02/03. AMT power operations were failing due to (1) missing management subnet in MaaS and (2) OpenSSL legacy TLS renegotiation disabled on the rack controller. Deploy was rejected on ms01-02 because its old OS held the provisioning IP (ARP conflict). nuc-1 was permanently removed from all config after giving up on making it commission reliably.

## Changes

- **`infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/fix-maas-amt-ssl.yaml`** — Rewrote to patch `/etc/ssl/openssl.cnf` directly (system-wide, all processes) in addition to the pebble systemd drop-in. Added conditional MaaS API wait so it works on rack controller (no local API). Changed restart to `snap restart maas`.
- **`infra/maas-pkg/_tg_scripts/maas/configure-rack/playbook.configure-rack.yaml`** — Added `fix-maas-amt-ssl.yaml` include. The rack controller runs wsman for AMT operations — this was the missing fix that caused rackd/maas-agent to use default OpenSSL (legacy renegotiation blocked).
- **`infra/maas-pkg/_modules/maas_lifecycle_deploy/scripts/trigger-deploy.sh`** — Step 3 now queries BMC power state before deploy. If machine is ON (old OS running), powers it off and waits 15s to release the provisioning IP before issuing the deploy command.
- **`infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml`** — Added management subnet (10.0.11.0/24) to `managed_networks`. Removed all nuc-1 config: machine entry, 6 lifecycle unit entries, machine_paths entry, UniFi port 12 assignment.
- **`infra/pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/nuc-1/`** — Deleted entire unit tree (7 HCL files).
- **`scripts/ai-only-scripts/fix-maas-openssl-legacy-renegotiation/`** — New ad-hoc script applying the openssl.cnf patch to both live MaaS servers immediately.

## Root Cause

**AMT "Error determining BMC task queue"**: Two-layer failure. Primary: management subnet 10.0.11.0/24 missing from MaaS — Temporal power workflow couldn't find a rack controller for AMT BMCs at 10.0.11.x (`UnroutablePowerWorkflowException`). Secondary: rack controller's rackd/maas-agent spawned wsman without `OPENSSL_CONF` set (pebble doesn't propagate env to children), so OpenSSL 3.0+ blocked the legacy TLS renegotiation AMT requires.

**Deploy IP conflict**: MaaS does an ARP check on provisioning IPs before deploying. A machine with its old OS still running holds its fixed provisioning IP; the ARP check found it occupied and refused. Powering the machine off first releases the IP.

## Notes

- The fix for AMT SSL must be on BOTH region AND rack — region serves the API, rack spawns wsman. Previously only region had the fix.
- Patching `/etc/ssl/openssl.cnf` is more reliable than `OPENSSL_CONF` env var because system libssl reads it by default regardless of how the process was launched.
- nuc-1 GCS TF state was wiped and MaaS machine deleted before this commit. No orphaned state remains.
