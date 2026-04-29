# AMT boot override investigation for ms01-03

## Summary

Investigated why ms01-03 doesn't PXE boot despite AMT power commands succeeding.
Implemented CIM-based boot override in the auto-import script. Root cause: the AMT
"Force PXE Boot" override fires on the management NIC, which is not on the
provisioning VLAN (12). Physical intervention needed.

## What was found

### AMT connectivity confirmed
- AMT at `10.0.11.12` is reachable from MaaS server
- All wsman operations succeed (with system wsman + OPENSSL_CONF)
- Power-cycle commands accepted (`ReturnValue=0`)

### CIM boot override: fires but PXE on wrong interface
The full CIM boot override sequence was successfully implemented and tested:
1. `CIM_BootConfigSetting.ChangeBootOrder` — sets "Force PXE Boot" first → `ReturnValue=0`
2. `CIM_BootService.SetBootConfigRole(Role=1)` — marks as IsNext (one-time) → `ReturnValue=0`
3. `CIM_PowerManagementService.RequestPowerStateChange(10)` — hard reset → `ReturnValue=0`

After the hard reset, `AMT_BootSettingData.OptionsCleared=true` confirms the boot
override was consumed by the firmware. The machine rebooted.

**However**: no DHCP discover appeared on the provisioning VLAN (VLAN 12) from
ms01-03's MACs (`38:05:25:31:7f:15` or `38:05:25:31:7f:14`). The machine
completed booting (AMT reports power state 2 = ON) but did not enlist in MaaS.

### Root cause
Intel AMT "Force PXE Boot" boots via the **AMT management NIC** — the NIC that
AMT uses for its own connectivity. For ms01-03, AMT is reachable at `10.0.11.12`
(management VLAN 11). The management NIC is on VLAN 11, not VLAN 12 (provisioning).
PXE DHCP from the management NIC lands on VLAN 11 where there is no DHCP server,
so PXE fails and the machine falls back to booting from disk.

### Why UseNIC=true didn't work
`AMT_BootSettingData.UseNIC=true` (legacy BIOS approach) was also tried via wsman
PUT. The PUT succeeded but the field didn't persist in subsequent GETs — this field
only applies to legacy BIOS machines. The Minisforum MS-01 is UEFI-based
(`UEFIHTTPSBootEnabled=true`, `SecureBootControlEnabled=true`).

## Code changes (committed)

- `auto-import/run`: Added CIM boot override (ChangeBootOrder + SetBootConfigRole)
  before the power-cycle step. This is a best-effort improvement — it fires
  correctly but the NIC target is outside our control.
- `maas-machines-precheck/playbook.yaml`: Fixed wave filter bug (was checking
  `pxe.maas.machine-entries` instead of `maas.lifecycle.new`).

## Physical intervention required

### ms01-03 — BIOS PXE boot order
- AMT works; power-cycle + boot override fire correctly
- Need to set UEFI boot order to include the **provisioning VLAN NIC** as first
  boot option (the NIC connected to the UniFi port with `pxe_mgmt_public` profile)
- OR: investigate why the AMT management NIC is on a different switch port than
  the `pxe_mgmt_public` ports (3 and 6). The NIC connected to one of these ports
  should PXE-boot correctly once BIOS is set; verify physical cable routing.
- Also: check if switch port MAC assignments match physical connections (verify
  that MAC `38:05:25:31:7f:15` is actually on switch port 3, not another port)

### ms01-01 — AMT unreachable
- AMT at `10.0.11.10` is "Destination Host Unreachable" from MaaS server
- Either AMT is not configured in BIOS, or management VLAN is not on that switch port
- Need: configure AMT in BIOS OR add a smart plug (Tapo/Kasa) to that machine
- Until then, `power_type: manual` is correct but auto-import always times out

### nuc-1 — Smart plug works but machine doesn't auto-boot
- Smart plug at `192.168.1.225` cycles power (confirmed working)
- Machine doesn't boot automatically after power-cycle (BIOS power recovery = "stay off")
- Need: BIOS power recovery → "Power On" or "Last State"
- Need: BIOS boot order → PXE/network first

## Status

Wave `maas.lifecycle.new` is blocked on physical intervention for all 3 machines.
All automation code is correct and committed. Resume after physical access.
