# Fix AMT TLS legacy renegotiation and ms01-03 secrets

## Summary

Two bugs prevented ms01-03 from being power-cycled via AMT during the
`maas.lifecycle.new` auto-import hook. Fixed both.

## Changes

### 1. `infra/maas-pkg/_tg_scripts/maas/auto-import/run` — Use system wsman with OPENSSL_CONF

**Root cause**: The auto-import script's `_AMT_SCRIPT` used the snap-bundled
`/snap/maas/current/usr/bin/wsman`, which uses the snap's own OpenSSL library.
That library does not read `/etc/ssl/openssl.cnf` (the system OpenSSL config)
and cannot be configured to allow TLS legacy renegotiation. As a result, every
AMT connection attempt to port 16993 failed with:

```
SSL connect error: error:0A000152:SSL routines::unsafe legacy renegotiation disabled
```

**Fix**: Switch to the system `/usr/bin/wsman` (from the `wsmancli` apt package)
and set `OPENSSL_CONF=/var/snap/maas/common/openssl-legacy.cnf` in the subprocess
environment. The MaaS configure-server task (`fix-maas-amt-ssl.yaml`) already
writes this file and the systemd drop-in that exposes it to MaaS processes — we
just needed to also expose it to the manually-invoked wsman subprocess.

The system wsman uses a different flag format than the snap wsman:
- Old (snap): `wsman invoke -a MethodName -h host -P port -S --config-file ... -u user -p pw URI -J body`
- New (system): `wsman --endpoint https://user:pw@host:port --noverifypeer --noverifyhost --input - invoke --method MethodName URI`

**Confirmed working**: SSH to MaaS server, running system wsman with
`OPENSSL_CONF` set returns `<g:ReturnValue>0</g:ReturnValue>` (success).

### 2. `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg_secrets.sops.yaml` — Add ms01-03 power_pass

**Root cause**: The auto-import before_hook reads the AMT password from
`unit_secret_params` → `pwy-home-lab-pkg_secrets.config_params[<unit_path>].power_pass`.
ms01-03's `power_pass` was only present in `pwy-home-lab-pkg_secrets.providers.maas.config_params`
(the Terraform provider section), not in `config_params` (the unit-level section
that tg-scripts read via `unit_secret_params`). The before_hook got an empty
string and passed no password to wsman.

**Fix**: Added `power_pass: Minisforum123!!!` to the `config_params` section for
`pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-03`.

## Physical machine blockers (still require hardware intervention)

### ms01-01 — AMT unreachable
- AMT at 10.0.11.10: "Destination Host Unreachable" from MaaS server
- Management VLAN (10.0.11.x) port may not be connected, or AMT not configured in BIOS
- No smart plug configured — cannot power-cycle without physical access
- `power_type: manual` is correct for now; machine times out in auto-import every run

### ms01-03 — AMT reachable but machine doesn't PXE boot
- AMT wsman commands now succeed (PowerState=2 "power on" accepted)
- Machine powers on but does not appear in MaaS DHCP within 300s timeout
- Likely cause: BIOS boot order has disk first; machine boots to installed OS instead of PXE
- Needs physical access to set BIOS boot order to PXE first

### nuc-1 — Smart plug works but machine doesn't auto-boot
- Smart plug at 192.168.1.225 (via proxy) cycles power successfully
- Machine doesn't boot automatically; BIOS "power recovery" is likely "stay off"
- Needs: (1) BIOS power recovery → "Power On" or "Last State", (2) boot order → PXE first

## Status

Wave `maas.lifecycle.new` still failing due to the three physical machine issues.
All code fixes are committed; resuming wave run once physical machines are configured.
