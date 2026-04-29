# MaaS commissioning automation: structural robustness fixes

**Date:** 2026-04-09  
**Waves affected:** `pxe.maas.machine-entries` (wave 10)  
**Files modified:**  
- `infra/maas-pkg/_modules/maas_machine/scripts/commission-and-wait.sh`
- `infra/maas-pkg/_tg_scripts/maas/auto-import/run`
- `infra/maas-pkg/_tg_scripts/maas/configure-machines/tasks/power-on-machine.yaml`
- `docs/idempotence-and-tech-debt.md`

## Context

A systematic audit of the MaaS commissioning automation identified several structural
problems that prevented first-run success. These are fixes applied after wave 10 failed
repeatedly despite individual machine commissioning scripts working in isolation.

## Fix 1: SSH host key mismatch blocks commissioning (CRITICAL)

`commission-and-wait.sh` used `StrictHostKeyChecking=no` on all SSH calls to the MaaS
server, but `StrictHostKeyChecking=no` does NOT bypass failures when a host key has
CHANGED (only when it is unknown). After `make clean`/`make clean-all`, the MaaS server
VM is re-provisioned with a new host key, causing ALL SSH calls in commission-and-wait.sh
to fail with "REMOTE HOST IDENTIFICATION HAS CHANGED".

**Symptom:** All `_maas_status` calls return "unknown" (the SSH catch-all), so the
commissioning poller never sees the machine reach "Ready".

**Fix:** Added `_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"`
and replaced all 26 `ssh -o StrictHostKeyChecking=no` occurrences with `ssh ${_SSH_OPTS}`.
Also cleared the stale key from `~/.ssh/known_hosts` for the current session.

**Tech-debt note added** to `docs/idempotence-and-tech-debt.md`: `make clean`/`make clean-all`
should automatically run `ssh-keygen -R <maas_server_ip>` after destroying the MaaS server VM.

## Fix 2: Power-off skipped when power state is "unknown" (CRITICAL)

`_webhook_power_cycle` and `_amt_power_cycle` both checked `live_state != "on"` and
returned 0 (no-op) when the power state was "unknown". A Kasa smart plug that is
unreachable returns "unknown" from MaaS's `query-power-state`. This caused the commission
trigger to skip power-off, meaning MaaS sent a power-on to a machine that was ALREADY ON —
a no-op — so the machine never PXE booted and returned to New after the commissioning wait.

**Fix:** Changed both functions to only skip power-off when state is explicitly "off".
"unknown" and "on" both trigger a power-off attempt with the existing 120s wait loop.

## Fix 3: Polling intervals too slow

The main commissioning wait used a 30s polling interval, and the auto-import enlistment
poller also used 30s. Given that commissioning takes 5-15 minutes, the 30s interval meant
each status check was delayed by 30s after the previous one completed (~32-35s effective).

**Fix:** Reduced both to 10s. The framework default is 15s; 10s is aggressive but reasonable
given each SSH status call takes 2-5s.

## Fix 4: Interface configuration silently succeeds on failure (HIGH)

`_configure_interfaces` returned 0 (success) if it couldn't read the machine's interfaces
from MaaS (`|| { echo WARNING; return 0; }`). This left the machine in Ready state with no
configured network interfaces. The deploy step then failed with a cryptic MaaS 400 error:
"Node must be configured to use a network".

**Fix:**
1. Added retry loop (3 attempts, 15s delay) for the interface read — MaaS API can be briefly
   unavailable immediately after commissioning completes.
2. Changed `return 0` to `return 1` on all failure paths.
3. Added a check that at least one interface was actually configured before returning.
4. Changed all callers from `_configure_interfaces` to `_configure_interfaces || exit 1`.

## Fix 5: Commission trigger error handling too narrow (MEDIUM)

`_trigger_commission` only checked for "not available" in the MaaS commission response.
Other rejection reasons (bad request, invalid power driver, validation errors) were silently
ignored, causing the script to wait 15 minutes before detecting the failure.

**Fix:** Expanded the error pattern to: `"not available|bad request|cannot be commissioned|
invalid.*power|no power driver|validation error"`. Also now logs the exit code when the
commission command returns non-zero (without failing hard — MaaS may still have accepted it).

## Fix 6: auto-import silent timeout (MEDIUM)

When `wait_and_import` timed out (machine didn't appear in MaaS within the timeout),
it printed "Timeout — proceeding without import" and returned normally. The Terragrunt
before_hook exited 0, so `tofu apply` ran and failed confusingly ("resource not found").

**Fix:** Changed to `sys.exit(1)` with a clear error message. The before_hook now fails
fast with an actionable message about checking PXE boot and provisioning VLAN.

## Fix 7: Smart plug failures block all subsequent machines (MEDIUM)

In `power-on-machine.yaml`, the AMT/IPMI/Redfish power-on tasks all had `failed_when: false`
(soft failure), but the smart_plug power-on tasks did not. If ms01-01's Kasa plug at
192.168.1.226 is unreachable, the smart_plug OFF task fails, stopping the include_tasks
loop and preventing all subsequent machines from being powered on.

**Fix:** Added `failed_when: false` to both smart plug OFF and ON tasks, plus a debug
warning task that logs the failure with a hint about the AMT fallback.

## Fix 8: Stuck-commissioning recovery doesn't wait for power-off

When a machine was stuck in Commissioning (timed out), the recovery path (lines 829-836)
sent a power-off command via MaaS CLI then immediately slept only 10 seconds before
resetting status to New and re-triggering commissioning. The next iteration called
`_webhook_power_cycle`, but with fix #2 above, "unknown" power state now triggers another
power-off attempt with the 120s wait loop. However, we also added an explicit
`wait_for_condition` in the recovery path itself for clarity and to avoid race conditions
when the power type is AMT (which uses a different check function).

## Tech-debt note added

Added entry in `docs/idempotence-and-tech-debt.md` documenting that `make clean`/`make clean-all`
leaves stale SSH known_hosts entries for the MaaS server IP, requiring manual `ssh-keygen -R`
or relying on `UserKnownHostsFile=/dev/null` (now implemented in commission-and-wait.sh but
not in all scripts).
