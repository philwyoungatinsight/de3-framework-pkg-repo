# Fix: commission-and-wait.sh wsman binary and WoL fallback for AMT-broken machines

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Fixed two issues in `commission-and-wait.sh` that caused physical machine commissioning to fail
silently when AMT power management is unavailable:

1. **`_amt_power_on` wsman binary not found** — Python script invoked
   `/snap/maas/current/usr/bin/wsman` directly, which fails with `FileNotFoundError` outside
   snap confinement (snap squashfs is lazily mounted; the path is not reliably accessible in
   non-interactive SSH sessions spawned by Terraform local-exec).  Switched to the system
   `wsmancli` package (`/usr/bin/wsman`).

2. **No fallback when AMT TLS is broken** — eg83cp (ms01-02) has a broken AMT TLS stack
   (port 16993 accepts TCP but TLS handshake hangs for 90 s then times out).  Even with a
   working wsman binary, the machine cannot be powered on via AMT.  Added Wake-on-LAN as
   a fallback: after wsman fails, sends WoL magic packets on the provisioning VLAN interface
   to wake machines that support WoL from S5.

3. **`wsmancli` not installed on MaaS server** — added `wsmancli` to the `install-maas.yaml`
   Ansible task so it is installed idempotently on every `make` run.

## Root Causes

### Bug 1: snap wsman path not accessible in subprocess context

The MaaS snap ships `wsman` inside its squashfs image at
`/snap/maas/current/usr/bin/wsman`.  The `current` symlink resolves to the versioned dir
(`/snap/maas/41649/`), and the binary is there.  But the snap squashfs is **lazily mounted**:
it may not be mounted in the mount namespace of a non-interactive SSH session that Terraform
local-exec starts.  When Python calls `subprocess.run(['/snap/maas/current/usr/bin/wsman',
...])`, Linux resolves the path in the caller's mount namespace — if the squashfs is not yet
mounted, the file doesn't exist → `FileNotFoundError`.

Even when the squashfs IS mounted, running the snap binary outside the snap AppArmor profile
and with missing `LD_LIBRARY_PATH` causes "error while loading shared libraries: libwsman.so.1".

**Fix**: install the system `wsmancli` package (Ubuntu universe, `/usr/bin/wsman`), always
available without snap confinement requirements.

### Bug 2: AMT TLS broken on eg83cp (ms01-02)

eg83cp's AMT firmware has a broken TLS stack: port 16993 accepts TCP connections but the TLS
handshake never completes.  This causes:
- `query-power-state` → `state: 'unknown'` (90 s AMT query timeout)
- `wsman` connection → 30 s subprocess timeout → `sys.exit(1)` → `wsman_ok=0`
- Machine never powered on → stuck in "Commissioning" forever

Port 16992 (non-TLS AMT) is closed on this machine.  WoL magic packets on the provisioning
VLAN (where the PXE NIC lives) were tested; the machine's old DHCP lease showed it had booted
previously via PXE, but WoL from S5 does not appear to be reliably functional on this machine.

### Bug 3: `wsmancli` absent from configure-server playbook

The package was not listed in `install-maas.yaml`, so it was not installed on the MaaS server
after a `make clean-all && make`.  The old code referenced the snap binary path which had been
available in earlier setups; the system package was never explicitly added.

## Fixes

### Fix 1: Use system wsmancli

```python
# BEFORE:
snap = '/snap/maas/current'
conf = snap + '/etc/openwsman/openwsman_client.conf'
env = dict(os.environ,
           OPENSSL_CONF='/var/snap/maas/common/openssl-legacy.cnf',
           LD_LIBRARY_PATH=snap + '/usr/lib/x86_64-linux-gnu')
w = snap + '/usr/bin/wsman'

# AFTER:
# Use system wsmancli package — always available, no snap confinement required.
w = '/usr/bin/wsman'
conf = '/etc/openwsman/openwsman_client.conf'
env = os.environ.copy()
```

### Fix 2: WoL fallback after wsman failure

After `wsman_ok=0`, dynamically find the provisioning interface (the one with a 10.0.12.x
address), fetch the machine's PXE MAC from MaaS, and send magic packets on that interface.

```bash
_pxe_mac=$(ssh ... "${_MAAS} maas-admin interfaces read ${SYSTEM_ID} 2>/dev/null \
    | python3 -c 'import sys,json; ifaces=json.load(sys.stdin); \
      print(next((i["mac_address"] for i in ifaces if i.get("type")=="physical"), ""))'")
# Dynamic provisioning interface (not hardcoded):
_prov_iface=$(ip -o addr show | awk '/10\.0\.12\./{print $2}' | head -1)
_prov_bcast=$(ip -o addr show dev ${_prov_iface} | awk '{print $6}' | head -1)
wakeonlan -i "$_prov_bcast" "$_pxe_mac"
sudo etherwake -i "$_prov_iface" "$_pxe_mac"
```

### Fix 3: Add wsmancli to install-maas.yaml

```yaml
- name: Install wsmancli (required for AMT power-on in commission-and-wait.sh)
  ansible.builtin.apt:
    name: wsmancli
    state: present
    update_cache: false
  become: true
```

## Impact

- `_amt_power_on` no longer fails with `FileNotFoundError` — wsman calls now work for machines
  with functional AMT TLS
- Machines with broken AMT (eg83cp) get WoL magic packets as a fallback power-on attempt
- `wsmancli` is installed idempotently by configure-server — no manual package installation needed
- eg83cp (ms01-02) AMT TLS remains broken (hardware issue); WoL from S5 was tested but did
  not reliably wake the machine.  Physical intervention or AMT firmware reset is required to
  fully commission eg83cp autonomously.

## Files Changed

- `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`
- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/install-maas.yaml`
