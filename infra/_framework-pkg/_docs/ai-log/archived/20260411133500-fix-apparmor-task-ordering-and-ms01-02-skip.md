# Fix: AppArmor task ordering bug and ms01-02 skip-on-build

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.seed-server (wave 9), pxe.maas.machine-entries (wave 10)

## Summary

Two fixes committed:

1. **AppArmor task ordering bug** — the `Allow MaaS snap wsman to read /etc/xml/catalog`
   task in `install-maas.yaml` ran BEFORE `Install MaaS snap`. On a fresh deploy the
   profile file doesn't exist yet, so `grep -q` returned exit 2 (file not found ≠ no
   match), `sed` failed silently, `apparmor_parser` failed silently, but `echo "CHANGED"`
   still ran — so the task reported "CHANGED" while doing nothing. The MaaS snap then
   installed and created the profile WITHOUT our `/etc/xml/` rule, and AppArmor kept
   denying wsman's access to `/etc/xml/catalog`, causing the wsman OOM crash documented
   in `20260411091800-fix-maas-wsman-apparmor-oom-crash.md`.

   Fix: moved the AppArmor task to immediately AFTER `Install MaaS snap`. Also added an
   explicit `[ ! -f "$PROFILE" ]` guard that fails loudly instead of silently
   (so future ordering regressions are caught immediately). Changed `apparmor_parser -r`
   to `apparmor_parser --replace` (more explicit). Confirmed via live test that
   `snap restart maas` does NOT regenerate the AppArmor profile, so one application
   after snap install is sufficient.

2. **ms01-02 (eg83cp) skipped on build** — AMT TLS is broken: port 16993 accepts TCP
   but the TLS handshake hangs for 90 seconds before timing out. Port 16992 (non-TLS)
   is closed. Wake-on-LAN from S5 is not supported by this machine's BIOS.
   Without a working power-on mechanism, MaaS cannot commission the machine automatically.
   Set `_skip_on_build: true` on the ms01-02 entry in `pwy-home-lab-pkg.yaml`.
   Documented in `docs/idempotence-and-tech-debt.md`.

## Additional manual recovery (not codified)

During session debugging:
- Forced eg83cp from Commissioning to Failed commissioning state via postgres
  (`UPDATE maasserver_node SET status=2 WHERE system_id='eg83cp'`) to stop 90s timeout loops
- Released ms01-03 (reng4p) from stuck Deploying state via `maas maas-admin machine release`
  and removed `maas_instance.this` from TF state so next wave can redeploy cleanly

## Root Cause Detail

`install-maas.yaml` task order before fix:
```
AppArmor fix task (line 130)    ← profile file doesn't exist yet
Install MaaS snap (line 199)    ← creates profile WITHOUT our rule
maas init (line 204)
snap restart maas (line 264)    ← does NOT regenerate profile (confirmed)
```

`install-maas.yaml` task order after fix:
```
Install MaaS snap               ← creates profile (our rule not yet in it)
AppArmor fix task               ← adds /etc/xml/** r, and reloads (profile exists)
maas init
snap restart maas               ← safe: does not regenerate profile
```

## Files Changed

- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/install-maas.yaml`
  (moved AppArmor task after snap install, added explicit profile existence check)
- `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml`
  (added `_skip_on_build: true` for ms01-02/eg83cp)
- `docs/idempotence-and-tech-debt.md`
  (added tech-debt entry for eg83cp AMT TLS hardware defect)
