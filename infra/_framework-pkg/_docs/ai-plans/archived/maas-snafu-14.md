# Plan: maas-snafu-14 — Webhook BMC Task Queue Failure (localhost URL)

## What Broke

MaaS commissioning for nuc-1 failed with:

```
Error determining BMC task queue for machine t8wtg8
UnroutablePowerWorkflowException
```

After fixing the `trigger-commission.sh` power_type=manual override (snafu-13), the
actual webhook power control was attempted for the first time — and it failed because
MaaS couldn't find a rack controller for the BMC.

## Root Cause

MaaS's `get_temporal_task_queue_for_bmc()` (in `maastemporalworker/workflow/power.py`)
extracts the IP from the webhook `power_query_uri` URL to determine which rack controller
should handle the power operation. The webhook driver uses:

```python
ip_extractor = make_ip_extractor("power_query_uri", IP_EXTRACTOR_PATTERNS.URL)
```

In all machine `terragrunt.hcl` files, `_proxy` was hardcoded to `localhost`:

```hcl
_proxy = "http://localhost:7050"
```

This caused:
- `power_query_uri = "http://localhost:7050/power/status?host=..."`
- MaaS extracts `127.0.0.1` from the URL
- `127.0.0.1` is not on any managed VLAN subnet
- MaaS raises `UnroutablePowerWorkflowException` — no rack controller found
- Result: every webhook power operation fails

Additionally, `smart-plug-proxy.py` was binding on `127.0.0.1:7050` (loopback), so even
if the URL were correct, the MaaS rack controller couldn't reach it remotely.

## Why It Was Previously Hidden

The old `trigger-commission.sh` (pre-snafu-13) overrode `power_type=manual` before
commissioning — this caused MaaS to skip all BMC operations entirely. The localhost URL
was never exercised. After removing that workaround, the webhook URL bug became visible.

## Fix

**1. smart-plug-proxy.py bind address** (`configure-server` and `configure-region` copies):
- Added `HOST = os.environ.get("SMART_PLUG_HOST", "0.0.0.0")`
- Changed `app.run(host=HOST, port=PORT)` (was hardcoded `host="127.0.0.1"`)
- Updated docstring to document 0.0.0.0 default and rack controller requirement

**2. Terragrunt webhook URL** (all 5 machine `terragrunt.hcl` + 5 `deploying/terragrunt.hcl`):
- `_proxy = "http://localhost:7050"` → `_proxy = "http://${try(local.up.maas_host, "")}:7050"`
- This puts the MaaS server's real IP (10.0.10.11) in the webhook URLs
- MaaS extracts `10.0.10.11` → VLAN 10 subnet → rack controller found → success

**3. Immediate deployment** via `scripts/ai-only-scripts/update-smart-plug-proxy-bind/run`:
- SCPs updated proxy script to MaaS server and restarts the service
- Verified via `curl http://10.0.10.11:7050/health`

## Remaining Gaps

None. The fix is complete and deployed. The next wave run will set correct webhook URLs
in MaaS via Terraform.

## Machine State at Fix Time

- nuc-1: New (t8wtg8) — needs annihilation and rebuild to get correct webhook URLs applied
- ms01-01/02/03: Ready — already commissioned; their deploying webhook URLs will be
  updated on the next TF apply of the deploying wave
- pxe-test-vm-1: New — will pick up correct URLs on next commission run
