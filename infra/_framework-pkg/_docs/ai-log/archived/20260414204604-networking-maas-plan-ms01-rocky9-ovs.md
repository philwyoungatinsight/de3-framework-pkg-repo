# Plan: ms01-02 Rocky 9 + ms01-03 Ubuntu + OVS + MikroTik

## Summary

Researched current state of ms01-02/ms01-03 deployment and MikroTik networking work
from previous sessions. Fixed pre-flight gaps and wrote execution plan for deploying
both machines through the MaaS lifecycle + OVS automation.

## Changes

### `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml`

- Added DHCP reservations for ms01-02 and ms01-03 in the configure-region
  `dhcp_reservations` block:
  - `ms01-02-pxe`: `10.0.12.239`, MAC `38:05:25:31:81:10`
  - `ms01-03-pxe`: `10.0.12.238`, MAC `38:05:25:31:7f:14`
  These make provisioning IPs stable so the `configure-plain-hosts` wave can SSH to the
  correct address immediately after MaaS deployment.

- Set `bridges[0].nic: enp2s0f0np0` for ms01-02 (confirmed via `ip link` on live machine
  — 10Gbps, link UP, MAC `38:05:25:31:81:0e`, connected to CRS317 sfpplus3) and
  ms01-03 (inferred — identical MinisForum MS-01 hardware).

- Fixed YAML parse error: `_unit_purpose` for `configure-plain-hosts` contained
  `bridges: config` (unquoted colon), causing `ansible.builtin.include_vars` to fail.
  Wrapped value in single quotes and reworded to avoid the colon.

### `docs/idempotence-and-tech-debt.md`

Removed the ms01-02 AMT TLS tech-debt entry. AMT at 10.0.11.11 is confirmed working.

### `docs/ai-plans/networking-maas-ms01-rocky9-ovs.md` (new)

Execution plan for deploying ms01-02 (Rocky 9) and ms01-03 (Ubuntu 24.04) through the
full MaaS lifecycle + OVS configuration. Covers: configure-region (Rocky 9 image import
+ DHCP reservations), lifecycle waves, configure-plain-hosts wave, and verification.

## Current State

- ms01-02: alive at 10.0.12.238, running Ubuntu (prior deploy, NOT Rocky 9). Not in MaaS.
  Will be wiped and redeployed as Rocky 9 via the lifecycle waves.
- ms01-03: not deployed, not in MaaS.
- MaaS machine list: empty.
- All automation code is in place; plan is ready to execute via `/doit`.
