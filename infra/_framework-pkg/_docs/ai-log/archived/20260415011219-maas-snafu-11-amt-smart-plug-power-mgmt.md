# maas-snafu-11: AMT + Smart Plug Power Management Fix

**Date**: 2026-04-15  
**Commits**: `2845ee4a`

## What was done

Tracked and fixed two issues with AMT + smart plug power management for physical machines.

### Issue 1: Missing smart_plug_host for ms01-02 and ms01-03

ms01-02 (`192.168.2.105 tapo`) and ms01-03 (`192.168.2.210 tapo`) had no `smart_plug_host`
in config. The plug fallback was silently skipped when wsman failed on these machines,
causing the enrollment poll to time out waiting for all 4 machines.

**Fix**: Added `smart_plug_host` and `smart_plug_type` to both machines in
`infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml`.

### Issue 2: maas-machines-precheck bounced plug pre-emptively instead of as fallback

The old sequence:
1. If `mgmt_wake_via_plug` and AMT unreachable → bounce plug (first step, not fallback)
2. Run wsman
3. If wsman fails and has plug → raw plug

This bounced the plug even when AMT was already working, and did not retry wsman after
the bounce for `mgmt_wake_via_plug` machines.

**Fix**: Rewrote the AMT power cycle sequence in `maas-machines-precheck/playbook.yaml`:
1. **Try wsman first** for all AMT machines
2. If attempt 1 failed AND `mgmt_wake_via_plug: true`: bounce plug → wait up to 120s for AMT port 16993 → **retry wsman**
3. Last resort: raw plug cycle for any remaining failures with `smart_plug_host`

This matches the documented rule: plug restores standby power → AMT wakes up → AMT sets PXE boot override.

## Files changed

- `docs/ai-plans/maas-snafu-11.md` — documentation of machine power config and fix sequence
- `scripts/wave-scripts/default/test-ansible-playbooks/maas/maas-machines-precheck/playbook.yaml` — rewrote AMT power cycle sequence
- `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml` — added smart_plug_host/type for ms01-02 and ms01-03
