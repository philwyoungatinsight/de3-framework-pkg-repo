# AI Screw-up: UniFi Rate Limiter Disaster

## Summary

Three compounding mistakes during a session to fix UniFi port overrides resulted in destroyed TF state and a self-inflicted UDM login rate limit that persisted for over an hour.

## Mistakes

1. **Ran `tofu apply` directly in `.terragrunt-cache/`** — destroyed both `unifi_device.switches` resources from TF state (physical switches unaffected due to `forget_on_destroy = false`)
2. **Monkey-patched with one-off Python scripts** instead of fixing and running the null_resource automation
3. **Kept calling the UniFi API after rate limiting started** — every "diagnostic" call reset the window and made the outage longer
4. **Did not suggest rebooting the UDM** — suggested waiting 60 minutes instead

## Recovery

Reboot UDM (clears rate limiter in ~2 min), then one clean `terragrunt apply` on the device unit re-adopts both switches and runs the port-override patch script.

## CLAUDE.md additions needed

- Never run `tofu` directly in `.terragrunt-cache/` — always use `terragrunt`
- When UDM rate limiting triggers: stop all API calls, reboot UDM to recover
- See `docs/ai-screw-ups/README.md` for full account
