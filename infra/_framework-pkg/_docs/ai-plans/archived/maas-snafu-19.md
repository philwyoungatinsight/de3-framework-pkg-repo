# Plan: maas-snafu-19 — I226-V 10Mbps PXE Boot Failure (NIC Link Speed)

## Objective

ms01-02 commissioning was failing with `/dev/root: Can't open blockdev` because the
Intel I226-V NIC negotiated at 10Mbps during PXE boot. At 10Mbps, the 77MB initrd
takes ~62 seconds to download, but GRUB's PXE DHCP lease is only 30 seconds. GRUB
rebooted when the lease expired, never completing the initrd download. The fix is to
always bounce the smart plug at `commissioning:pre` (and `deploying:pre`) for
`mgmt_wake_via_plug` machines — even when AMT is already reachable — to guarantee the
NIC link is at 1000M before triggering PXE boot.

## Context

**Root cause chain:**
1. Intel I226-V NIC runs at 10Mbps in S5/WoL mode (no AMT standby power)
2. When AMT standby is active (AC power restored and AMT initialized), NIC runs at 1000M
3. Current precheck plug-bounce logic: bounce plug only when AMT port 16993 is unreachable
4. Gap: if AMT port happens to respond but NIC is still at 10M (or if machine was simply
   never bounced this session), the skip-if-reachable logic leaves the NIC at 10M
5. PXE DHCP lease on MaaS rack is 30 seconds for PXE clients (vendor-class "PXE")
6. 77MB initrd at 10Mbps ≈ 62 seconds → lease expires → GRUB reboots → can't open blockdev

**Evidence:**
- Apr 15 01:58 success: full 80MB initrd in ~6 seconds (13MB/s = 1000Mbps-class)
- Apr 16 18:59 failure: ~2.3MB in 23 seconds (~100KB/s = 10Mbps-class)
- Switch port query: ms01-02-port3 and ms01-02-port4 both at **10M** before bounce
- After smart plug bounce (this session): both ports at **1000M**, AMT at 16993 responsive
- Stale DHCP reservation: ms01-02's DHCP hostname is `rsvd-2` (created during initial
  enrollment under temp name) — needs annihilate+re-enroll to clean up

**Hardware:** ms01-02: Intel I226-V 2.5GbE (MAC 38:05:25:31:81:10), AMT at 10.0.11.11:16993,
smart plug Tapo P125 at 192.168.2.105, `mgmt_wake_via_plug: true`.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/playbook.yaml` — modify

Change the "Restore AMT standby via smart plug before BMC check" task.

**Current behavior**: skip plug bounce if AMT port 16993 responds. This leaves a gap
where AMT is reachable but NIC is at 10M.

**New behavior**: for `commissioning:pre` and `deploying:pre`, ALWAYS bounce the plug
for `mgmt_wake_via_plug` machines (unconditional). Then wait up to 120s for AMT to
respond. The machine is expected to be powered off at these waves, so bouncing is safe.

For other waves/states (transitional state annihilation path), keep the old "bounce
only if unreachable" behavior to avoid bouncing deployed machines.

**Exact change** — replace the shell block in "Restore AMT standby via smart plug":

Old logic (simplified):
```bash
if nc -z -w5 "$AMT" 16993; then
  echo "AMT reachable — no bounce needed"
  exit 0
fi
# bounce + wait for AMT
```

New logic (simplified):
```bash
ALWAYS_BOUNCE="{{ _gate_wave in ['commissioning', 'deploying'] and _gate_mode == 'pre' }}"
if [ "$ALWAYS_BOUNCE" = "False" ] && nc -z -w5 "$AMT" 16993; then
  echo "AMT reachable and not a mandatory-bounce wave — no bounce needed"
  exit 0
fi
# bounce + wait for AMT (always bounces for commissioning:pre and deploying:pre)
```

Also update the log messages to be clear about whether it was a mandatory or recovery bounce.

## Execution Order

1. Read the current playbook (lines 259-312) to confirm exact text
2. Apply the change using Edit
3. Annihilate ms01-02: delete from MaaS (system_id rbr4nf) + wipe GCS TF state
4. Re-run `./run -b -w "*maas.lifecycle.commissioning*"` (smart plug already bounced, NIC at 1000M)
5. Monitor commissioning: confirm initrd downloads completely, machine reaches Ready

## Verification

- Switch port shows ms01-02-port3/port4 at 1000M when commissioning fires
- MaaS commissioning completes: machine reaches Ready status
- No `/dev/root: Can't open blockdev` in MaaS commissioning log
- Gate commissioning:pre log shows "Bouncing smart plug" even when AMT was initially reachable
