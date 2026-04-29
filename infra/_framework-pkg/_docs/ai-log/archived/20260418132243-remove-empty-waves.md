# Remove Empty Waves — external.servers, external.storage, external.power

## Summary

Removed three vestigial waves that had no units assigned to them: `external.servers`,
`external.storage`, and `external.power`. All three were defined in `maas-pkg.yaml`
and listed in `waves_ordering.yaml` but never actually gated any Terraform units,
making them silent no-ops on every build.

## Changes

- **`config/waves_ordering.yaml`** — removed three wave entries
- **`infra/maas-pkg/_config/maas-pkg.yaml`** — removed three wave definitions
- **`infra/proxmox-pkg/_docs/README.md`** — removed `external.servers` row from wave table and "why wave separation matters" note that referenced it

## Notes

`external.servers` was intended to verify pve-1/pve-2 are reachable, but those
node units carry no `_wave:` field so they run as foundation units in every wave.
`external.storage` was an explicit placeholder for future NAS/SAN management.
`external.power` had a `power-mgmt/power-mgmt-test` playbook referenced but
no units to run it against — the playbook script remains on disk but is now unreferenced.
