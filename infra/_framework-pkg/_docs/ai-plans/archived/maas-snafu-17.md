# Plan: maas-snafu-17 — Commissioning Stuck in PXE Loop + "Failed to query BMC" During Scripts

## What Broke

Two recurring failures in ms01-02 commissioning:

### Failure 1: Machine stuck in PXE boot loop, never loads ephemeral

After our snafu-16 fix (removing `_amt_direct_boot` pre-boot), the machine correctly enters
Commissioning state via AMT, but fails to load the ephemeral commissioning image.

Pattern observed:
- Multiple PXE boot cycles every ~35 seconds
- GRUB downloads kernel (15MB) and sometimes initrd (8.5MB) via HTTP
- But the commissioning image kernel fails to boot and/or the machine hangs at GRUB prompt
- Machine goes silent (no DHCP, no HTTP) for 25+ minutes

Root cause analysis: In cycle N+1, GRUB downloads boot-kernel but NOT boot-initrd (network
blip at that exact moment). Machine reaches a GRUB error prompt and waits indefinitely. MaaS
timeout is 90 minutes so it doesn't auto-recover.

The grub.cfg uses `[::1]:5248` and `[::1]:8000` as server addresses, which rely on the
commissioning initrd setting up local proxies. When these proxies aren't set up (because
the machine never fully boots), the commissioning image can't download root filesystem.

### Failure 2: "Failed to query node's BMC" during commissioning script execution

After ephemeral loads successfully and commissioning scripts start:
- At ~10-14 minutes into commissioning: `Failed to query node's BMC (admin) - Aborting COMMISSIONING`
- MaaS rack controller's wsman gets `SSL connect error` polling AMT every ~35 seconds
- AMT's SSL stack fails under machine load (commissioning scripts: lshw, blkid, smart tests)
- MaaS decides the machine is unreachable and aborts

Timeline of failures (from MaaS events):
- 09:48 ephemeral loaded → 10:02 cloud-init failure (pkg install — transient)
- 10:07 ephemeral loaded → 10:20 Failed to query BMC
- 10:34 ephemeral loaded → 10:45 Failed to query BMC
- 10:56 stuck in PXE, never loaded ephemeral

## Fix Applied

### For Failure 1: Annihilate and re-run
- Delete ms01-02 from MaaS
- Remove GCS TF state for machine + commission units
- Re-run wave to re-enroll and recommission

### For Failure 2: Need investigation
- Root cause: MaaS's AMT power polling every ~35s during commissioning
- When commissioning scripts run CPU-intensive tasks, AMT's SSL stack drops connections
- After enough SSL failures, MaaS fires `_start_bmc_unavailable` errback which aborts
- Short-term: monitor and retry if it fails again
- Long-term: consider setting machine's power_type to `manual` during commissioning and
  reverting to `amt` after Ready (but this conflicts with config-as-source-of-truth rule)
- Alternative: investigate MaaS's `node_timeout` and AMT query interval settings

## Open Questions

1. Is there a MaaS config to reduce AMT polling frequency during commissioning?
2. Can the commissioning scripts be parallelized less aggressively to reduce CPU/IO load
   and thus reduce AMT SSL timeouts?
3. Should `testing_scripts=none` be passed to reduce commissioning load? (We already do this)

## Remaining Gaps

- The `package_update_upgrade_install` cloud-init failure at 10:02 was transient (packages
  installed fine in later attempts). No code fix needed for this.
- The PXE loop issue (Failure 1) is likely a transient network blip. If it recurs
  consistently, investigate GRUB retry logic and network reliability on provisioning VLAN.
- Failure 2 needs a systematic fix to prevent AMT polling failures from aborting commissioning.
