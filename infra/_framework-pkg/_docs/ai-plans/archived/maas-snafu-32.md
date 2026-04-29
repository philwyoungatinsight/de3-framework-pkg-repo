# Plan: maas-snafu-32 — zzz_1_cloud_init_success Silently Skips Due to Wrong Reporting Config Path

## Root Cause

During Rocky 9 deployment, the `zzz_1_cloud_init_success` curtin late_command is meant
to send a `finish/modules-final/SUCCESS` event to MaaS BEFORE poweroff. This prevents the
SIGTERM-triggered failure signal (snafu-26: when `zzz_poweroff` runs `poweroff`, systemd
sends SIGTERM to the ephemeral cloud-final.service, and cloud-init reports "failed: final"
to MaaS → "Node installation failure").

The script reads OAuth credentials from:
```
${TARGET}/etc/cloud/cloud.cfg.d/90_maas_cloud_init_reporting.cfg
```

However, when curtin injects cloud-init configs into the target OS (via the
`cloudconfig:` block in the curtin config), it names them `50-cloudconfig-{key}.cfg`,
not the `90_*` paths specified in the config. The actual file written to the target is:
```
${TARGET}/etc/cloud/cloud.cfg.d/50-cloudconfig-maas-reporting.cfg
```

Evidence from MaaS pebble journal (wtqnp8 deployment):
```
cloud-init[1428]: Injecting cloud-config:
cloud-init[1428]: {'maas-reporting': {'content': '...', 'path': '50-cloudconfig-maas-reporting.cfg'},
                   'maas-datasource': {'content': '...', 'path': '50-cloudconfig-maas-datasource.cfg'},
                   ...}
```

The script found no file at `90_maas_cloud_init_reporting.cfg`, logged:
```
WARNING: /tmp/.../etc/cloud/cloud.cfg.d/90_maas_cloud_init_reporting.cfg not found — skipping (non-fatal)
```
...and exited 0 without sending the success signal.

`zzz_poweroff` then ran, SIGTERM hit cloud-final.service, cloud-init reported "failed:final",
and MaaS marked the machine as "Failed deployment".

Note: The actual OS installation (grub2, dracut, fstab, etc.) succeeded completely.
The failure was entirely in the MaaS reporting pathway.

## Fix

Update `zzz_1_cloud_init_success` in `curtin_userdata_rocky9.j2` to try both paths:
1. `90_maas_cloud_init_reporting.cfg` (curthooks handle_cloudconfig for RHEL osfamily)
2. `50-cloudconfig-maas-reporting.cfg` (curtin cloud-config injection path)

Use whichever exists. If neither exists, exit 0 (still non-fatal).

## Files Modified

### `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/templates/curtin_userdata_rocky9.j2` — modified

- Changed `zzz_1_cloud_init_success` to search both candidate paths
- Updated comment to reference snafu-32 and document both paths

## Verification

- configure-region log should show preseed deployed successfully
- MaaS pebble journal during deployment should show:
  `Found reporting config at: .../50-cloudconfig-maas-reporting.cfg`
  `MaaS success:final sent — HTTP 200`
- MaaS events should NOT show "Node installation failure"
- ms01-02 should reach Deployed state

## Open Questions

None — ready to implement.
