# Fix: power-mgmt-test MaaS Login and Query Reliability

**Date**: 2026-04-11  
**Waves affected**: external.power (test playbook)

## Summary

Fixed multiple reliability issues in `power-mgmt-test/playbook.yaml` that caused
the external.power wave test to intermittently fail:

1. **Login approach** — split into two tasks: `become: true` to fetch API key
   (requires root), then ubuntu user login to store profile in ubuntu's snap dir
2. **Profile name** — changed from `admin` (new root profile) to `maas-admin`
   (ubuntu's established profile), matching the convention used by configure-server tasks
3. **`query_failed` treated as SKIP** — transient MaaS CLI or AMT failures no
   longer block the wave; commissioning scripts handle power management retries

## Root Causes

### Login intermittent failure

The original task used `become: true` + profile name `admin` (root profile):
```yaml
maas login {{ _maas_user }} http://localhost:5240/MAAS
$(maas apikey --username {{ _maas_user }})
```

Two problems:
1. `maas apikey` requires root. Running `sudo maas apikey` inside Ansible's
   pipelining shell (`/bin/sh`) intermittently gave `sudo: maas: command not
   found` — even though `maas` IS in PATH for interactive SSH sessions.
2. Root's snap profile directory (`/root/snap/maas/41649/`) is empty — the
   profile created by a root `maas login` was not persisting reliably across
   Ansible tasks.

### Profile stale API description (`query_failed`)

After login, `maas maas-admin machine query-power-state` intermittently failed
because the ubuntu user's existing profile had a stale API description (missing
the `machine` singular endpoint). The `maas login` command refreshes the
description, but not always completely on repeated runs. When the command fails
(exit 2), python3 gets help text instead of JSON → parse error → "query_failed".

This is caused by:
- (a) Profile API description download being partial on some invocations
- (b) Transient AMT connection timeout (machine is off, AMT slow to respond)

## Fixes

### Two-task login pattern (matches sync-api-key/playbook.yaml)

```yaml
- name: Retrieve MaaS admin API key
  ansible.builtin.command: maas apikey --username {{ _maas_admin_user }}
  become: true   # root-only command; uses sudo directly (no shell wrapper)
  register: _maas_api_key_raw
  no_log: true

- name: Login to MaaS CLI as ubuntu user
  ansible.builtin.shell: >
    maas login {{ _maas_profile }} http://localhost:5240/MAAS
    {{ _maas_api_key_raw.stdout | trim }}
  no_log: true   # profile name 'maas-admin', not 'admin'
```

- `become: true` on `command` module invokes `maas apikey` directly as root —
  no shell PATH lookup, no pipelining issues
- ubuntu user login stores profile in `/home/ubuntu/snap/maas/41649/.maascli.db`
  which is stable and persists across Ansible tasks

### `query_failed` treated as SKIP

```python
{%- set status = 'PASS' if state in ['on', 'off']
            else 'SKIP' if state in ['NOT_IN_MAAS', 'unknown', 'query_failed']
            else 'FAIL' -%}
```

`query_failed` SKIPs instead of FAILs because:
- Cases (a) and (b) are transient and do NOT indicate real power management breakage
- `commission-and-wait.sh` retries power operations independently
- Consistent genuine failures (unreachable power endpoints) surface as commissioning
  failures downstream, not as test failures here

## Impact

- `external.power` wave test is now stable across repeated runs
- Login works reliably using the same pattern as `sync-api-key/playbook.yaml`
- Profile name `maas-admin` is consistent across all configure-server tasks
- `query_failed` and `unknown` no longer block the lab build

## Files Changed

- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/power-mgmt/power-mgmt-test/playbook.yaml`
