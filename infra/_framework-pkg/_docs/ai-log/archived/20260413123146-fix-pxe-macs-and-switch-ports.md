# Fix: pxe_mac_address was set to AMT NIC (port3) instead of data NIC (port4)

## Problem

All three MS-01 machines had `pxe_mac_address` set to the wrong NIC MAC, and
`machine-onboarding.md` had wrong switch ports and wrong switch for AMT NICs.

Discovered via `scripts/ai-only-scripts/query-unifi-switch` (new tool, see below).

## MS-01 port layout (now confirmed from live switch data)

Each MS-01 has two NICs connected to the USW-Flex-2.5G-8:
- **Physical port 3 = i226-LM (AMT NIC)** → USW-Flex ports 1/2/3, `pxe_mgmt_public`
- **Physical port 4 = i226-V (data NIC)** → USW-Flex ports 4/5/6, `pxe_mgmt_public`

Both are on VLAN 11 (`pxe_and_mgmt`, 10.0.11.0/24) which carries both PXE
provisioning traffic and AMT management traffic.

PXE boot uses the data NIC (port4, i226-V) — the machine's BIOS PXE-boots from
this NIC. The AMT NIC (port3, i226-LM) is management-only.

On ms01-01, the AMT NIC link goes DOWN due to a firmware bug and only recovers
after an AC power cycle via the Tapo smart plug. The USW-Flex port 1 shows
"last known MAC: a3" in the UniFi GUI but speed=0 until the machine is rebooted.

## MAC addresses (corrected)

| Machine | Port4 MAC (PXE, data NIC) | Port3 MAC (AMT NIC) | USW-Flex PXE port | USW-Flex AMT port |
|---------|--------------------------|---------------------|-------------------|-------------------|
| ms01-01 | 38:05:25:31:2f:**a2** | 38:05:25:31:2f:**a3** | 4 | 1 |
| ms01-02 | 38:05:25:31:81:**10** | 38:05:25:31:81:**11** | 5 | 2 |
| ms01-03 | 38:05:25:31:7f:**14** | 38:05:25:31:7f:**15** | 6 | 3 |

## Changes

### `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml`

- ms01-01 `pxe_mac_address`: `...a3` → `...a2` (data NIC, USW-Flex port 4)
- ms01-02 `pxe_mac_address`: `...81:11` → `...81:10` (data NIC, USW-Flex port 5)
- ms01-03 `pxe_mac_address`: `...7f:15` → `...7f:14` (data NIC, USW-Flex port 6)

### `infra/maas-pkg/_docs/machine-onboarding.md`

- Machines table: corrected PXE switch ports (ms01-01: 2→4, ms01-02: 4→5)
- AMT NIC table: corrected switch from "USW-Pro-Max-16" to "USW-Flex" and
  corrected port numbers (now 1/2/3 for ms01-01/02/03)
- Added note about ms01-01 AMT firmware bug causing link dropout

### New: `scripts/ai-only-scripts/query-unifi-switch/`

Reusable Ansible playbook that queries the UniFi controller API for live
switch port data (link speed + MAC address table per port). Credentials are
read from SOPS-encrypted config. Use `SWITCH_FILTER=Flex ./run` to filter.

### `CLAUDE.md`

Added `query-unifi-switch` to the existing scripts list with a rule:
use this script (not one-off curl commands) whenever live switch port or
MAC information is needed.
