# Fix: Debian image import failing due to MaaS snap AppArmor confinement

**Date:** 2026-04-09  
**Waves affected:** `pxe.maas.seed-server` (wave 9)  
**Files modified:** `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/import-debian-image.yaml`, `infra/maas-pkg/_tg_scripts/maas/configure-server/ansible.cfg`, `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-*`

## Root Cause

The Debian image import workflow downloads a qcow2, runs `qemu-nbd` to mount it via a block device (`/dev/nbd0`), chroots into it to install EFI packages and a standard kernel, then converts it to a gzipped raw image for MaaS import.

The qcow2 was stored in `/var/snap/maas/common/debian-import/` because MaaS CLI (snap) requires files to be in `SNAP_COMMON` to read them at import time.

**The problem:** MaaS snap uses **strict AppArmor confinement**. `qemu-nbd` runs *outside* the snap boundary. When it connects to a qcow2 file in `/var/snap/maas/common/`, it opens the file read/write. As data is written to `/dev/nbd0` (e.g. by `apt-get install` in the chroot), qemu-nbd writes COW cluster changes back to the qcow2 file. AppArmor blocks these writes because the qcow2 path is inside snap's confinement zone but the writer (qemu-nbd) is outside it.

Result: after `qemu-nbd --disconnect`, the qcow2 was inaccessible or appeared deleted, causing `qemu-img convert` to fail with "No such file or directory".

### Secondary issues fixed in earlier sessions
- `wget -c` flag caused rc=56 (server rejected Range requests) → removed `-c`
- `command: mv` with `become: true` failed writing to snap dir → replaced with `ansible.builtin.copy remote_src: true`
- SSH disconnects during long playbook → `ansible.cfg` with `ControlMaster=no`, `retries=15`, pipelining
- DHCP enable race condition → retry loop on `vlan update`

## Fix

Move all intermediate files (`_qcow2`, `_raw`, `_rawgz`) to `/tmp`. Only the final `.img.gz` (read-only at MaaS import time) is copied to the snap common dir via `ansible.builtin.copy` with `become: true` immediately before the `maas` CLI import call.

This means qemu-nbd operates entirely on `/tmp` files, which are not subject to snap AppArmor restrictions.

### Key variable layout after fix
```yaml
_qcow2:      "/tmp/{{ item.name | replace('/', '-') }}.qcow2"
_raw:        "/tmp/{{ item.name | replace('/', '-') }}.img"
_rawgz:      "/tmp/{{ item.name | replace('/', '-') }}.img.gz"
_rawgz_dest: "{{ _debian_tmp }}/{{ item.name | replace('/', '-') }}.img.gz"
```

Only `_rawgz_dest` lives in `/var/snap/maas/common/debian-import/`.

## Result

Wave 9 (`pxe.maas.seed-server`) succeeded on the next run:
- Debian trixie qcow2 downloaded to `/tmp` (no `-c` flag)
- qemu-nbd connected, chroot apt-get install completed
- `qemu-img convert` succeeded (both `/tmp` paths)
- gzip succeeded
- `.img.gz` copied to snap dir
- `maas maas-admin boot-resources create` succeeded
- Test playbook: "PASS: 11 boot resource(s) available"
