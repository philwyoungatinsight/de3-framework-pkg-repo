# Fix: auto-import hook loops on tainted maas_instance during deploy

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.machine-entries (wave 10)

## Summary

Wave 10 entered an infinite destroy+create loop for ms01-03 (reng4p). Every time
`maas_instance.this: Creating...` started, the MaaS HTTP API (port 5240) became
temporarily unavailable (~30-40 seconds), causing the TF provider to fail with
`connection refused`. TF tainted `maas_instance.this`. On the next retry the
before_hook saw "Deploying + in state" and returned True (skipping import), so
TF destroyed+recreated — triggering the same API crash in a loop.

## Root Cause: MaaS API crash during AMT power-cycle

When `maas_instance.this: Creating...` runs, MaaS internally sends AMT commands
(wsman at port 16993) to power-cycle the machine. During this operation, the
`maas-http` nginx process briefly crashes and restarts (~30-40 second outage).

Evidence:
- pebble health checks show `http: active` at 11:30:51.648 (200 OK)
- TF gets `dial tcp 10.0.10.11:5240: connect: connection refused` at 11:30:51.885
  (only 237ms after pebble confirmed health)
- 27-second gap in maas-http access logs (11:30:45 → 11:31:21)
- pebble polls every 30s so it misses the nginx restart window
- Machine IS successfully PXE-booting (DHCP discovery at 11:31:21 confirms progress)

The crash does NOT prevent deployment — the machine PXE-boots and installs Ubuntu
normally. Only TF's polling connection is affected.

## Root Cause: Hook returned True for "Deploying + in state"

The `check_and_clean_state` function's `else` branch (machine not in
`non_deployed_statuses`) had a simple `else` clause when `maas_instance.this`
was already in state: it logged "skipping import" and returned True.

For a tainted resource, this meant TF would:
1. Find tainted `maas_instance.this` → plan destroy+create
2. Destroy: send RELEASE (10s, machine released from "Deploying" to "Ready")
3. Create: send deploy → AMT power-cycle → MaaS API crashes again
4. TF gets connection refused → taints again
5. Wave runner retries → same loop

## Fix

When `live_status == "Deploying"` AND `maas_instance.this` IS in state:
1. Wait up to `_MAAS_DEPLOY_WAIT_TIMEOUT` (default 1800s) for machine to reach "Deployed"
2. Once Deployed: `tofu state rm maas_instance.this` (removes any taint)
3. `tofu import maas_instance.this <id>` (re-imports fresh, no taint)
4. Return True → next apply is a no-op

This breaks the destroy+create loop by waiting for the in-progress deployment to
complete naturally, then updating TF state to reflect reality.

## General Rule

When `maas_instance.this` is in state (possibly tainted) AND the machine is
"Deploying":
- Do NOT let TF apply run — it will destroy+recreate, causing another AMT crash
- Wait for "Deployed" in the before_hook
- Remove and re-import `maas_instance.this` to clear any taint
- The AMT crash is transient; the machine will finish deploying on its own

## Files Changed

- `infra/maas-pkg/_tg_scripts/maas/auto-import/run`
  (added wait+refresh logic in the `else` branch when `maas_instance.this` is in
   state and machine is "Deploying")

## Session context

The AMT password loss fix (direct postgres UPDATE) was already committed and
documented in `20260411152900-fix-maas-deploy-stuck-amt-password.md`.

ms01-03 (reng4p) reached "Performing PXE boot" at 15:36:23 UTC during the current
session — the 4th deploy attempt succeeded in sending the machine to PXE. The
wave will be re-run after "Deployed" status is reached.
