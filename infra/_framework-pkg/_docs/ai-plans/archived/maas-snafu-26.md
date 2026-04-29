# Plan: maas-snafu-26 — Rocky 9 "Failed deployment" Due to cloud-init SIGTERM Race

## Root Cause

Curtin installation of Rocky 9 **succeeds completely** — grub2-install wrapper works,
all late_commands pass, `netboot_off` is signaled. But MaaS still marks the node as
"Failed deployment" due to this race:

1. `zzz_poweroff` (last late_command) runs `poweroff`
2. Systemd starts shutdown and sends SIGTERM to `cloud-final.service` (PID 1432)
3. cloud-init receives SIGTERM mid-cleanup (after curtin completes but before cloud-init
   can report success)
4. cloud-init's SIGTERM handler sends `failed: final` webhook to MaaS
5. MaaS transitions Deploying → Failed deployment

Evidence from syslog at 13:34:03:
```
cloud-init[1432]: curtin: Installation finished.
cloud-init[1432]: Running command ['umount', '/tmp/tmpd3dy2ls0/target']
cloud-init[1432]: Received signal 15 resulting in exit. Cause:
  subprocess.py _try_wait line 2011
```

The `failed: final` arrives after `netboot_off` but before MaaS can see `success: final`.
Once MaaS gets `failed: final` while in Deploying state, it marks as Failed deployment.

## Why This Doesn't Affect Ubuntu/Debian

For Ubuntu/Debian custom images: the installed system's own cloud-init sends `success: final`
on first boot. The ephemeral cloud-init doesn't report final status because Ubuntu's
deployment model doesn't rely on ephemeral-cloud-init's final stage.

For Rocky 9 (custom tgz + `base_image=rhel/9`): curtin runs within the ephemeral Ubuntu
24.04 cloud-final.service. Curtin's `zzz_poweroff` kills the cloud-final.service before
it can report success.

## Fix

Add a late_command `zzz_1_cloud_init_success` (alphabetically between `zz_signal_maas`
and `zzz_poweroff`) that:

1. Reads the MaaS reporting credentials from `$TARGET/etc/cloud/cloud.cfg.d/90_maas_cloud_init_reporting.cfg`
   (written by curtin's `handle_cloudconfig()` for RHEL osfamily during curthooks)
2. Sends the `success: final` webhook POST to MaaS using OAuth1 PLAINTEXT authentication
3. Exits 0 regardless — must not block poweroff

When MaaS receives `success: final` before `poweroff`, the node transitions to Deployed
state. The subsequent SIGTERM-triggered `failed: final` is ignored because the node is
already Deployed.

## Files Modified

### `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/templates/curtin_userdata_rocky9.j2` — modified
### `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/templates/curtin_userdata_rocky9.j2` — modified

Add `zzz_1_cloud_init_success` late_command between `zz_signal_maas` and `zzz_poweroff`:

```yaml
  # Send cloud-init 'success: final' to MaaS BEFORE poweroff to avoid the race where
  # zzz_poweroff triggers SIGTERM → cloud-init reports 'failed: final' → Failed deployment.
  #
  # This runs AFTER zz_signal_maas (netboot disabled) but BEFORE zzz_poweroff.
  # Alphabetical ordering: 'zzz_1' < 'zzz_p' ✓
  #
  # Credentials from $TARGET/etc/cloud/cloud.cfg.d/90_maas_cloud_init_reporting.cfg
  # which curtin's handle_cloudconfig() writes for RHEL osfamily during curthooks.
  # Non-fatal: exits 0 even on error so poweroff still runs.
  zzz_1_cloud_init_success:
    - python3
    - -c
    - |
      import json, os, re, sys, time, urllib.request, urllib.error, random

      LOG = '/tmp/curtin-late.log'
      def log(msg):
          print(msg)
          try:
              with open(LOG, 'a') as f: f.write(msg + '\n')
          except Exception: pass

      log('--- zzz_1_cloud_init_success: sending success:final to MaaS ---')
      target = os.environ.get('TARGET_MOUNT_POINT', '')
      reporting_cfg = os.path.join(target, 'etc/cloud/cloud.cfg.d/90_maas_cloud_init_reporting.cfg')

      if not os.path.exists(reporting_cfg):
          log(f'WARNING: {reporting_cfg} not found — skipping (non-fatal)')
          sys.exit(0)

      content = open(reporting_cfg).read()
      m_ep = re.search(r'endpoint:\s*(\S+)', content)
      m_ck = re.search(r'consumer_key:\s*(\S+)', content)
      m_tk = re.search(r'token_key:\s*(\S+)', content)
      m_ts = re.search(r'token_secret:\s*(\S+)', content)
      if not all([m_ep, m_ck, m_tk, m_ts]):
          log('WARNING: could not parse reporting credentials — skipping (non-fatal)')
          sys.exit(0)

      endpoint   = m_ep.group(1)
      consumer_k = m_ck.group(1)
      token_k    = m_tk.group(1)
      token_s    = m_ts.group(1)

      nonce = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=16))
      auth = (
          f'OAuth realm="",'
          f'oauth_consumer_key="{consumer_k}",'
          f'oauth_token="{token_k}",'
          f'oauth_signature_method="PLAINTEXT",'
          f'oauth_timestamp="{int(time.time())}",'
          f'oauth_nonce="{nonce}",'
          f'oauth_version="1.0",'
          f'oauth_signature="&{token_s}"'
      )
      payload = json.dumps({
          'event_type': 'finish', 'name': 'modules-final',
          'result': 'SUCCESS', 'timestamp': time.time(),
          'description': 'running modules for final', 'origin': 'cloudinit',
      }).encode('utf-8')

      try:
          req = urllib.request.Request(endpoint, data=payload, method='POST',
              headers={'Authorization': auth, 'Content-Type': 'application/json'})
          with urllib.request.urlopen(req, timeout=10) as resp:
              log(f'MaaS success:final sent — HTTP {resp.status}')
      except Exception as e:
          log(f'WARNING: failed to send success signal: {e}')
      log('--- zzz_1_cloud_init_success done ---')
```

## Open Questions

None — root cause confirmed from syslog evidence.

## Verification

- During deployment: `zzz_1_cloud_init_success` should appear in MaaS events (or curtin log)
- `MaaS success:final sent — HTTP 204` (or 200) in `/var/log/curtin-late-debug.log`
- ms01-02 should reach Deployed state (not Failed deployment)
