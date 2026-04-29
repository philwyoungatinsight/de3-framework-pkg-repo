# Fix: Waves Sticky Header (v2) + MaaS Annihilation Grace Period + NET-1 skip_ssh_check

## Summary

Two bugs in `maas-lifecycle-gate` caused ms01-02 to be repeatedly annihilated or its
`deployed:post` gate to fail after a successful Rocky 9 deployment. Also shipped the
second attempt at fixing the waves panel sticky header, which moves scroll responsibility
into `rx.table.root` itself instead of the parent `waves_content` box.

## Changes

- **`infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/playbook.yaml`**
  — Three fixes:
  1. Added `skip_ssh_check` to `_all_machines` dict so the field flows through to gate checks.
  2. Extended the 60-second grace period (pause + MaaS re-read + filter) to cover `Deploying`
     candidates in addition to `Commissioning` candidates. The filter now removes `Deploying`
     machines that transitioned to `Deployed` or `Ready` during the pause.
  3. Added `rejectattr('skip_ssh_check', 'equalto', true)` to the NET-1 SSH check loop so
     machines with `skip_ssh_check: true` (e.g. ms01-02, which waits at GRUB after deploy)
     are skipped in the `deployed:post` reachability check.

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`** — Second
  attempt at sticky header fix. Replaced `overflow="visible"` approach with making
  `rt-TableRoot` the actual scroll container: `height="100%"` + `overflow_y="auto"` on
  both `rx.table.root` calls; removed `overflow_y="auto"` from `waves_content` box. CSS
  `position:sticky` anchors to the nearest scroll-container ancestor — this makes
  `rt-TableRoot` that ancestor.

- **`docs/ai-plans/maas-snafu-18.md`** — Plan documenting both root causes and fixes
  (archived below with the commit).

## Root Cause

**Annihilation**: The annihilation filter after the 60-second grace period only removed
`Commissioning` candidates that had transitioned to a safe state. `Deploying` machines
were passed through unconditionally (`else: always include`), even if MaaS had already
marked them `Deployed` during the pause. This matters for `mgmt_wake_via_plug` machines
where curtin signals MaaS (`zz_signal_maas`) before powering off, then the smart plug
cuts AC — the gate can see `Deploying` + BMC=off for a narrow window.

**NET-1**: `skip_ssh_check` was not included in `_all_machines` and not filtered in the
NET-1 loop. ms01-02 waits at the GRUB screen after deploy (long GRUB_TIMEOUT), so SSH
port 22 is not open when `deployed:post` fires. The `skip_ssh_check: true` flag in config
was silently ignored.

**Sticky header**: The first fix (`overflow="visible"` on `rx.table.root`) likely didn't
work because Radix's CSS may override the prop or the DOM hierarchy still didn't give
sticky a proper containing block with a definite height. The second approach puts the
definite height AND the overflow scroll on the same element that wraps the `<thead>`, so
CSS sticky has an unambiguous scroll container.

## Notes

- The grace period for `Deploying` candidates uses the same 60-second wait as
  `Commissioning`. This is sufficient because `zz_signal_maas` runs before `zzz_poweroff`,
  so MaaS should already reflect `Deployed` by the time the gate re-reads.
- The `not (status == 'Deploying' and _gate_wave == 'deployed')` exclusion already
  protects `Deploying` machines at the `deployed:pre` gate specifically; the grace period
  adds a second layer of protection for the intermediate window.
