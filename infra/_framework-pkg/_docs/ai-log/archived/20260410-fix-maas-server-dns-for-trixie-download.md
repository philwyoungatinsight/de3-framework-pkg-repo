# Fix MaaS server DNS failure blocking Debian Trixie image download

**Date:** 2026-04-10
**Files modified:**
- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/import-debian-image.yaml`

## Problem

The `pxe.maas.seed-server` wave fails every run at the Trixie image download step:

```
TASK [Download custom/trixie qcow2 image to /tmp]
fatal: [maas-server-1]: FAILED! => {"rc": 4, "stderr": "", "stdout": ""}
```

`wget rc=4` = network failure. Duration: ~65 seconds = the `--timeout=60` hit once, then wget exited. No stderr at all. Pattern is consistent with DNS resolution timeout, not a connection reset or server error.

**Root cause:** MaaS snap installs its own bind9 DNS service on port 53. After installation and initialization, the system DNS resolver on the MaaS server is pointed at MaaS's bind9. This bind9 instance handles provisioning-VLAN hostnames for DHCP/PXE. For external names like `cloud.debian.org`, it needs working forwarders.

At the point in the configure-server playbook where the Trixie image download runs (after MaaS is installed, networking configured, API key synced), MaaS's DNS may not yet have working external forwarding—either because:
1. Its bind9 forwarders aren't configured to reach upstream DNS
2. The default route interface's DNS was overwritten by MaaS setup

Result: `getaddrinfo('cloud.debian.org')` times out → wget fails with rc=4.

**Evidence from log:**
- Download task ran for 65 seconds (one 60s timeout attempt)
- rc=4 with empty stderr (DNS timeout signature—not a server error or partial download)
- The "already imported — skipping" task correctly showed `skipping: [maas-server-1]` (image NOT in MaaS, confirming a fresh configure-server run, not an idempotency bug)

## Fix

Added a pre-download DNS check task inside the import block, before the Pre-flight cleanup:

```yaml
- name: "Ensure external DNS resolves for {{ item.name }} download"
  ansible.builtin.shell: |
    if python3 -c "import socket; socket.setdefaulttimeout(5); socket.getaddrinfo('cloud.debian.org', 443)" 2>/dev/null; then
      echo "DNS OK — cloud.debian.org resolves"
      exit 0
    fi
    # DNS failing — add Google DNS to the default-route interface via resolvectl.
    # resolvectl dns is non-destructive: sets link-level DNS without modifying config
    # files or restarting services. Works alongside MaaS's bind9.
    IFACE=$(ip route get 8.8.8.8 2>/dev/null | awk '/dev/{print $5; exit}')
    if [[ -n "$IFACE" ]]; then
      resolvectl dns "$IFACE" 8.8.8.8 8.8.4.4 2>/dev/null || true
      sleep 1
    fi
  become: true
  changed_when: false
```

Also increased wget timeout from 60s to 120s and retries from 10 to 5 with 30s delay (fewer, longer retries suit large binary downloads better than many rapid retries).

## Why resolvectl dns (not /etc/resolv.conf patching)

- `resolvectl dns <iface> <servers>` sets per-link DNS for an interface without touching config files or restarting systemd-resolved
- Non-destructive: existing resolvers remain, Google DNS is added alongside them
- No SSH disruption risk (unlike restarting resolved or applying netplan)
- Works even if systemd-resolved already has MaaS DNS configured
