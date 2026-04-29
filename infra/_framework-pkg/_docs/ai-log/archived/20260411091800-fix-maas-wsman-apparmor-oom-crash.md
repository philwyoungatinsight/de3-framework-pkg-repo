# Fix: MaaS snap wsman AppArmor OOM crash causing "connection refused" errors

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Fixed two issues that caused cascading MaaS API failures during physical machine
commissioning/deployment:

1. **`wsman` OOM crash under snap AppArmor** — MaaS's internal AMT power driver
   forks the snap-bundled `wsman` binary under the `snap.maas.pebble` AppArmor
   profile. The profile denied `/etc/xml/catalog` read access (needed by libxml2).
   This caused wsman to either segfault (stack overflow in XML error handler) or
   leak ~1.8GB RAM before being OOM-killed. The OOM kill cascaded to MaaS pebble
   service restart (~30s outage), causing Terraform's MaaS provider to get
   "connection refused" or "connection reset by peer" errors mid-apply.

2. **WoL heredoc bug** — The `_prov_bcast: unbound variable` crash from the
   prior fix (double-quoted SSH command string expanded remote variables locally in
   `set -u` context) was already fixed in commit 38bebed. This log documents that
   fix plus the AppArmor fix discovered in the same wave run.

## Root Cause

### Bug 1: snap.maas.pebble AppArmor profile missing `/etc/xml/**`

MaaS's AMT power driver (`provisioningserver/drivers/power/amt.py`) calls:
```python
def _get_wsman_command(self, *args):
    base_path = snap.SnapPaths.from_environ().snap or "/"
    return ("wsman", "-C",
            join(base_path, "etc/openwsman/openwsman_client.conf"),
    ) + args
```

`"wsman"` with no full path resolves via PATH to the snap's own bundled binary at
`/snap/maas/current/usr/bin/wsman`. The child process inherits the parent's
AppArmor profile (`snap.maas.pebble`). The bundled libxml2 in wsman tries to
open `/etc/xml/catalog` (XML entity catalog), which AppArmor denies.

Consequences:
- `wsman` segfaults at `0x7ffffffe` (stack overflow in XML error handler) for
  most invocations — observed in kernel log at 09:04:38–09:06:35 UTC
- One invocation (pid 881345) leaked **1,925,076 kB virtual, 1,867,904 kB RSS**
  before being OOM-killed at 09:10:44 UTC
- OOM kill cascaded: MaaS pebble service restarted at 09:11:17 UTC
- During restart window: Terraform MaaS provider got "connection refused" /
  "connection reset by peer" on in-flight API requests for ms01-01 release and
  ms01-03 maas_instance create

Kernel log evidence:
```
Apr 11 09:10:44 kernel: postgres invoked oom-killer
Apr 11 09:10:45 kernel: oom-kill: task=wsman,pid=881345,uid=0
Apr 11 09:10:45 kernel: Out of memory: Killed process 881345 (wsman)
                        total-vm:1925076kB, anon-rss:1867904kB
Apr 11 09:11:17 systemd: Started snap.maas.pebble.service
```

AppArmor audit log evidence (repeated every ~5 min per commissioning attempt):
```
kernel: apparmor="DENIED" operation="open" profile="snap.maas.pebble"
        name="/etc/xml/catalog" comm="wsman"
```

### Bug 2: WoL double-quote local expansion (fixed in 38bebed)

`_amt_power_on` WoL fallback used `ssh ... "...script containing $_prov_bcast..."`.
Bash expanded `$_prov_bcast` locally before SSH ran. Since `set -u` is active in
commission-and-wait.sh and `_prov_bcast` is not defined locally (only remotely),
the script crashed with:
```
./scripts/commission-and-wait.sh: line 408: _prov_bcast: unbound variable
```

## Fixes

### Fix 1: AppArmor local override for snap.maas.pebble

Added idempotent AppArmor rule insertion to `install-maas.yaml`:

```yaml
- name: Allow MaaS snap wsman to read /etc/xml/catalog (AppArmor fix)
  ansible.builtin.shell: |
    PROFILE=/var/lib/snapd/apparmor/profiles/snap.maas.pebble
    if ! grep -q '/etc/xml/' "$PROFILE"; then
      sed -i '/^\s*\/etc\/mime\.types r,/a\  \/etc\/xml\/{,**} r,\n  \/etc\/openwsman\/{,**} r,' "$PROFILE"
      apparmor_parser -r "$PROFILE"
      echo "CHANGED"
    else
      echo "OK"
    fi
  changed_when: "'CHANGED' in _apparmor_wsman_fix.stdout"
```

The rule is inserted after `  /etc/mime.types r,` which is a stable anchor line.
`apparmor_parser -r` reloads the live profile without restarting MaaS.

Snapd regenerates `/var/lib/snapd/apparmor/profiles/snap.maas.pebble` on snap
refresh, so this task re-applies idempotently on each `configure-server` run
(which runs after the MaaS snap install task above it).

Also applied immediately on the live server during the wave run:
```bash
sed -i '/^\s*\/etc\/mime\.types r,/a\  \/etc\/xml\/{,**} r,...' PROFILE
apparmor_parser -r PROFILE
```

### Fix 2: WoL bash heredoc (commit 38bebed)

Changed `_amt_power_on` WoL code from double-quoted SSH string to
`ssh ... bash -s << WSSEOF` heredoc. Remote variables prefixed with `\$` to
defer expansion. `set +eu` at start of remote script (WoL is best-effort).
`${_pxe_mac}` expanded locally (set as literal in heredoc body).

## Impact

- MaaS snap no longer OOM-crashes when AMT power operations are retried
- wsman can access `/etc/xml/catalog` without AppArmor denial
- "connection refused" / "connection reset by peer" Terraform errors due to
  MaaS restart should not recur
- WoL fallback no longer crashes commission-and-wait.sh with unbound variable

## Files Changed

- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/install-maas.yaml`
  (AppArmor rule addition)
- `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`
  (WoL heredoc fix — already committed in 38bebed)
