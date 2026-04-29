# Fix: MaaS deployment stuck due to missing AMT password in BMC record

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

ms01-03 (reng4p) was stuck in "Deploying" state for 44+ minutes with no PXE boot
events. MaaS could not power-cycle the machine because the AMT password was missing
from the `maasserver_bmc` table. The `power_pass` field was empty despite the YAML
having the correct password — it was cleared during multiple release/commission cycles.

## Root Cause

After multiple release/recommission cycles (from concurrent wave runs and the
auto-import hook fix session), the AMT power parameters in MaaS's BMC record had
the `power_address` and `power_user` but an empty `power_pass`. When MaaS received
the deploy command (from `maas_instance.this` CREATE), it attempted to power-cycle
the machine via AMT. With no password, wsman failed, and the machine never rebooted
into the PXE environment. MaaS set status to "Deploying" but the machine sat idle.

## Detection

- Machine in "Deploying" state for 44+ minutes
- No PXE boot events ("Performing PXE boot", "Loading ephemeral", etc.)
- Machine ping: 100% packet loss
- `maas machine query-power-state reng4p` → initially timed out
- Database query: `SELECT b.power_parameters FROM maasserver_bmc b JOIN maasserver_node n ON n.bmc_id = b.id WHERE n.system_id='reng4p'` → `{"port": "16993", "power_user": "admin", "power_address": "10.0.11.12"}` (no power_pass)

## Fix

1. Updated the BMC record directly via postgres to add the missing password:
   ```sql
   UPDATE maasserver_bmc 
   SET power_parameters = power_parameters || '{"power_pass": "Minisforum123!!!"}'
   WHERE id = (SELECT bmc_id FROM maasserver_node WHERE system_id='reng4p') 
   AND power_type='amt'
   ```

2. Verified MaaS now can query AMT power state:
   ```
   maas maas-admin machine query-power-state reng4p → {"state": "on"}
   ```

3. Aborted the stuck deployment via `maas machine abort reng4p`

4. Forced machine status to Ready via postgres (status=4) since abort didn't fully
   take effect. The machine was then re-deployed via the next wave run.

## Additional Issue: Connection Reset During maas_instance CREATE

During the subsequent wave run, `maas_instance.this: Creating...` got:
```
read tcp 10.0.11.146:49896->10.0.10.11:5240: read: connection reset by peer
```

MaaS processed the deploy (machine transitioned to "Deploying" at 15:23:26) but the
TF provider's TCP connection was reset. TF partially saved `maas_instance.this` to
state before the error, then cleaned up by sending RELEASE.

The second auto-apply (triggered by TF retrying) detected the drift (maas_instance.this
in state but machine in "Releasing"), planned destroy+create, and the cycle continued
correctly.

## Root Cause for AMT Password Loss

The commission-and-wait.sh script restores power_parameters after commissioning. But
during the rapid release/commission/deploy cycles (caused by concurrent wave runs and
repeated failures), the restore may have failed or the MaaS state may have been reset
by an intermediate commissioning that cleared the BMC credentials.

## Prevention

1. **No concurrent wave runs**: Only one `./run` invocation should be active at a time.
   Multiple concurrent runs on the same wave cause 409 Conflicts and state races.

2. **The auto-import wait loop fix** (committed d348dbc) prevents the most common cause
   of the problem: the hook no longer allows TF to CREATE maas_instance.this when the
   machine is already "Deploying".

3. **Known risk**: If commission-and-wait.sh fails to restore AMT power_pass during a
   commissioning cycle, subsequent deploys will silently fail. The fix would be to add
   explicit AMT password restoration to the deploy path as well.

## General Rule

When a MaaS machine is stuck in "Deploying" with no PXE events for >10 minutes:
1. Check `maas machine query-power-state` — if timeout/error, AMT credentials may be missing
2. Check AMT credentials via API: `maas maas-admin machine power-parameters <system_id>`
3. If credentials missing, restore via API: `maas maas-admin machine update <system_id> power_type=amt power_parameters='{"power_address":"...","power_user":"admin","power_pass":"..."}'`
4. Use `maas machine abort <system_id>` to abort the stuck deployment
5. Use `maas machine release <system_id>` if abort doesn't work (machine returns to Ready)
6. Re-run the wave

**Note**: The original fix used direct postgres UPDATEs (`UPDATE maasserver_bmc`, `UPDATE maasserver_node`).
These are no longer the recommended approach — use the MaaS CLI API instead.
See `CLAUDE.md` "Delete-Automate-Recreate" section for the current rule.

## Files Changed

No code files changed — this was a runtime data fix via database and MaaS CLI.
The auto-import hook wait loop fix was already committed in d348dbc (same session).
