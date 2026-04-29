# Fix MaaS Webhook BMC Task Queue Failure (localhost URL)

## Summary

After fixing the `trigger-commission.sh` power_type=manual override (snafu-13), MaaS
commissioning for nuc-1 failed with "Error determining BMC task queue." Root cause:
webhook `power_query_uri` URLs used `localhost:7050` so MaaS extracted `127.0.0.1` as
the BMC IP — not on any managed subnet — and couldn't find a rack controller for the
Temporal power workflow. Fixed by using `maas_host` IP in all webhook URLs and binding
`smart-plug-proxy` to `0.0.0.0` instead of `127.0.0.1`.

## Changes

- **`infra/maas-pkg/_tg_scripts/maas/configure-server/smart-plug-proxy/smart-plug-proxy.py`** — Added `HOST = os.environ.get("SMART_PLUG_HOST", "0.0.0.0")`; changed `app.run(host=HOST, ...)` to use it; updated docstring explaining 0.0.0.0 requirement
- **`infra/maas-pkg/_tg_scripts/maas/configure-region/smart-plug-proxy/smart-plug-proxy.py`** — Same changes (copy of configure-server version)
- **All 5 machine `terragrunt.hcl` files** (nuc-1, ms01-01/02/03, pxe-test-vm-1) — `_proxy = "http://localhost:7050"` → `_proxy = "http://${try(local.up.maas_host, "")}:7050"`
- **All 5 `deploying/terragrunt.hcl` files** — Same `_proxy` fix
- **`scripts/ai-only-scripts/update-smart-plug-proxy-bind/run`** — Created ai-only-script to immediately deploy the proxy fix to the MaaS server (SCPs updated script, restarts service, verifies health endpoint)
- **`docs/ai-plans/maas-snafu-14.md`** — Documents root cause, fix, and how the bug was previously hidden by the power_type=manual workaround

## Root Cause

MaaS's `get_temporal_task_queue_for_bmc()` extracts the IP from the webhook
`power_query_uri` URL. `localhost` → `127.0.0.1` → not on any managed VLAN subnet →
`UnroutablePowerWorkflowException`. This was previously hidden by the old
`trigger-commission.sh` which overrode `power_type=manual` before commissioning,
bypassing all BMC operations.

## Notes

- Proxy fix was deployed immediately via the ai-only-script (not waiting for full MaaS server re-run)
- nuc-1 was annihilated (delete from MaaS + GCS state removal) so TF will re-import it with correct webhook URLs on the next build
- Discovered new physical issue: nuc-1 did not auto-start after smart plug cycle — switch port shows DOWN. Machine may require physical power button press if "Power on after AC loss" BIOS setting is not functioning correctly.
