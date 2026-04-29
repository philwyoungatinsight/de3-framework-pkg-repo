# maas-machines-precheck: pre-wave playbook now owns machine enrollment

## Summary

The `maas-machines-precheck` pre-wave playbook for `maas.lifecycle.new` now
fully owns physical machine enrollment in MaaS — power-cycling unenrolled
machines and waiting for them to PXE enlist before the wave's Terragrunt units
run.  The Terragrunt before-hook (`auto-import/run`) is reduced to TF state
management and import only (skips power-cycling if the machine is already in
MaaS).

## Architecture before this change

- **Pre-wave playbook**: state review + normalization only
- **before-hook**: power-cycling + MaaS enrollment wait + TF state management

Problem: the before-hook has no access to the pre-wave's view of machine
state. It always power-cycled (potentially disrupting a machine the pre-wave
had just enrolled), then waited the full 300 s timeout per machine.

## Architecture after this change

- **Pre-wave playbook**: state normalization + power cycling + MaaS enrollment wait
- **before-hook**: tries import immediately (pre-wave may have enrolled it); only
  power-cycles + waits if the machine is still not in MaaS

## Changes

### New: `infra/maas-pkg/_tg_scripts/maas/amt-power-cycle/run`

Standalone Python script extracted from the `_AMT_SCRIPT` embedded in
`auto-import/run`.  Takes `<amt_ip>` as argv[1] and `AMT_PASS` from env.

Used by the pre-wave Ansible playbook via `ansible.builtin.script`, which
transfers the file to the MaaS server and runs it there.  The MaaS server has
`wsman` installed and can reach the management VLAN (10.0.11.0/24).

OpenSSL legacy renegotiation workaround (`OPENSSL_CONF`) is passed via env.

### `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-machines-precheck/playbook.yaml`

**Play 1** — `_all_machines` builder overhauled:
- Replaces three separate builders (`_all_machines`, `_amt_machines`,
  `_smart_plug_machines`) with a single comprehensive list
- Adds `path`, `pxe_mac_address`, `amt_address`, `mgmt_wake_via_plug`,
  `smart_plug_host`, `smart_plug_type`, and `power_pass` (from
  `_tg_providers_secrets`) to each entry
- Secrets are passed to AMT tasks via `environment:` with `no_log: true`

**Play 2** — State normalization (unchanged) + new task:
- `Identify machines not yet enrolled in MaaS` → `_machines_not_in_maas` list
  used by Plays 3, 4, 5

**Play 3** — "Power cycle AMT machines not yet in MaaS" (replaces "Check AMT
reachability"):
1. Filters `_machines_not_in_maas` to AMT machines
2. For `mgmt_wake_via_plug` machines: shell task checks AMT port 16993; if
   unreachable, bounces smart plug (off → 5s → on), polls up to 120s for AMT
3. Runs `amt-power-cycle/run` via `ansible.builtin.script` for all AMT
   machines to enroll; `AMT_PASS` env var, `no_log: true`

**Play 4** — "Power cycle smart-plug machines not yet in MaaS" (simplified):
- Only cycles plugs for machines NOT in MaaS (dropped the "is it off?" query)
- Machines already in MaaS (even if off) are left alone

**Play 5** — NEW "Wait for unenrolled machines to appear in MaaS":
- Polls MaaS by PXE MAC address every 15 s
- Timeout: `_MAAS_ENROLL_WAIT_TIMEOUT` env var (default 300 s)
- Fails with a clear troubleshooting message listing which machines did not
  appear (check BIOS boot order, switch port, AMT reachability, plug proxy)

### `infra/maas-pkg/_tg_scripts/maas/auto-import/run` — `main()` change

After `check_and_clean_state` returns False (machine not in TF state), the
hook now attempts `_find_and_import` immediately before power-cycling:

```python
if _find_and_import(maas_host, mac_address):
    sys.exit(0)
```

If the pre-wave enrolled the machine, this imports it and exits 0 without
power-cycling.  If not found, proceeds with the original power-cycle + wait
path as a fallback.

## Flow for a clean run

```
pre-wave plays 1–2: load config, normalise bad MaaS states
pre-wave play 3:    wsman PXE boot each AMT machine not in MaaS
pre-wave play 4:    cycle smart plug for each smart-plug machine not in MaaS
pre-wave play 5:    wait until all MACs appear in MaaS (≤300s)
  → wave Terragrunt units run
  → before-hook:  check_and_clean_state → not in TF state
                  _find_and_import → machine now in MaaS → import → done
                  (no power cycling)
```

## Status

`smart_plug_host` for ms01-01 is still `""`.  The mgmt_wake_via_plug plug
bounce in Play 3 will be skipped until the plug IP is set.  If AMT is
unreachable, the wsman attempt will fail and Play 5 will time out for ms01-01.
Once a smart plug is cabled and its IP set in YAML, the full flow will work.

Physical interventions still required before `maas.lifecycle.new` passes:
- ms01-01: smart plug cabled, `smart_plug_host` set in `pwy-home-lab-pkg.yaml`
- ms01-03: BIOS boot order → PXE first on provisioning NIC
- nuc-1: BIOS power recovery → auto-on; boot order → PXE first
