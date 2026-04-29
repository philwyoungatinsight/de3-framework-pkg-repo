# ai-only-scripts

AI-generated diagnostic, recovery, and one-off operational scripts. Not invoked
by the automation pipeline — run manually when needed.

Each directory contains a `run` entrypoint. Most support `--apply` / `--dry-run`
or `--build` / `--test` / `--clean` flags; check the header comment of each `run`
for usage.

## Scripts

# TODO: this is out of date after refactoring

| Script | Purpose |
|--------|---------|
| [`destroy-unifi-resources/`](destroy-unifi-resources/) | Delete VLANs, port profiles, and device port override assignments managed by unifi-pkg. Use when `make clean-all` cannot reach the controller or state was wiped but resources remain. Dry-run by default; pass `--apply` to delete. |
| [`fix-ms01-interface-link/`](fix-ms01-interface-link/) | Clear stale MaaS IP reservations on ms01-01 after a force-release left the interface in a broken state (`has a reserved ip but no link to subnet`). |
| [`import-unifi-networks/`](import-unifi-networks/) | Import existing UniFi VLAN networks into Terraform state after `make clean-all` wiped the state but left the networks on the controller (prevents `api.err.VlanUsed` on next apply). |
| [`push-debian-preseed/`](push-debian-preseed/) | Push an updated Debian trixie curtin preseed to the MaaS server after modifying `curtin_userdata_trixie.j2`. |
| [`recover-ms01-network/`](recover-ms01-network/) | Recover ms01 network connectivity after a failed network reconfiguration. |
| [`reset-ms01-01/`](reset-ms01-01/) | Force ms01-01 back to MaaS Ready state with disk erase and clear its Terraform state, for when the machine is stuck (Deploying, Deployed with no network, etc.). |
