# Fix: AMT Power-On Caller Params, Restore Format, and wsman Timeout

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Fixed three bugs in `commission-and-wait.sh` that caused MS-01 machines (ms01-02, ms01-03)
to not be powered on via AMT during commissioning retries:

1. **`_amt_power_on()` re-fetched power-parameters from MaaS after restore** — if the restore
   failed (see bug 2 below), MaaS still had `power_type=manual` and returned `{}` for
   power-parameters, causing wsman power-on to be silently skipped.
2. **AMT restore used wrong MaaS CLI format** — `power_parameters[key]=value` format returns
   `{"power_parameters": ["This field is required."]}`. MaaS requires a JSON string:
   `power_parameters={"key":"value"}`.
3. **wsman `subprocess.run()` had no timeout** — when AMT TLS didn't respond (ms01-02 at
   10.0.11.11:16993 was hanging), wsman hung indefinitely, blocking the entire script.

## Root Causes

### Bug 1: Circular re-fetch after failed restore

`_trigger_commission()` fetched AMT params from MaaS, set `power_type=manual`, triggered
commission, waited for Ready, then tried to restore `power_type=amt`. But:

1. Restore failed silently (bug 2)
2. `_amt_power_on()` re-fetched power-parameters from MaaS to get the endpoint/credentials
3. MaaS still had `power_type=manual` → returned `{}` for power-parameters
4. Python script detected empty `power_address` and printed "WARNING: skipping wsman power-on"
5. Machine was never powered on for deploy

### Bug 2: Wrong MaaS CLI format for power_parameters restore

```python
# BEFORE (rejected by MaaS API):
cmd = ["sudo", "maas", "maas-admin", "machine", "update", "${SYSTEM_ID}", "power_type=amt"]
for k, v in params.items():
    cmd.append("power_parameters[{}]={}".format(k, v))

# MaaS returns: {"power_parameters": ["This field is required."]}
```

Also: restore Python didn't call `sys.exit(r.returncode)`, so bash `|| echo WARNING` never
fired even when the restore failed.

### Bug 3: wsman hangs when AMT TLS doesn't respond

ms01-02 (10.0.11.11:16993) accepts TCP connections but TLS handshake hangs indefinitely.
`subprocess.run()` with no timeout blocks the script permanently, stalling the entire wave.

## Fixes

### Fix 1: Pass caller params to `_amt_power_on()` as `$1`

```bash
_amt_power_on() {
    local _caller_params="${1:-}"
    local _caller_params_b64=""
    if [ -n "$_caller_params" ] && [ "$_caller_params" != "{}" ]; then
        _caller_params_b64=$(printf '%s' "$_caller_params" | base64 -w0 2>/dev/null \
            || printf '%s' "$_caller_params" | base64 2>/dev/null)
    fi
    # ...
    # SSH heredoc uses caller params instead of re-fetching from MaaS:
    if [ -n "${_caller_params_b64}" ]; then
        printf '%s' "${_caller_params_b64}" | base64 -d | python3 /tmp/amt-poweron-${SYSTEM_ID}.py
    else
        sudo maas maas-admin machine power-parameters ${SYSTEM_ID} 2>/dev/null | python3 /tmp/amt-poweron-${SYSTEM_ID}.py
    fi
```

Call site updated:
```bash
_amt_power_on "$_amt_params_json"
```

### Fix 2: Use `power_parameters=<json>` format in restore

```python
# AFTER (accepted by MaaS API):
cmd = ["sudo", "maas", "maas-admin", "machine", "update", "${SYSTEM_ID}",
       "power_type=amt", "power_parameters=" + json.dumps(params)]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode:
    print(r.stderr, file=sys.stderr)
    sys.exit(r.returncode)
```

Also changed `>/dev/null 2>&1` to `2>&1` so errors surface in the log.

### Fix 3: wsman subprocess timeout

```python
try:
    r = subprocess.run(
        [w, '-C', conf, '--endpoint', endpoint,
         '--noverifypeer', '--noverifyhost',
         '--input', '-', 'invoke', '--method', method, uri],
        input=xml, env=env, capture_output=True, text=True, timeout=30)
except subprocess.TimeoutExpired:
    print('ERROR: wsman timed out after 30s — AMT TLS not responding.', file=sys.stderr)
    sys.exit(1)
```

After 30s timeout, the script exits with a clear error and falls through to the manual
power-on prompt ("Please MANUALLY POWER ON the machine now.").

## Impact

- AMT power params are reliably passed to wsman even after restore failure
- AMT restore now succeeds consistently (correct MaaS CLI format)
- wsman timeout prevents indefinite hang; operator gets a clear error + manual power prompt
- ms01-02 and ms01-03 commissioning retries now work correctly

## Files Changed

- `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`
