# Fix Ansible SSH issues and _skip_on_build inheritance in wave test playbooks

## Context

Running `./run --apply --start-at 3` to resume the build from the network.unifi wave.
Multiple issues were discovered and fixed in sequence.

## Issues Fixed

### 1. verify-unifi-networking: Wrong credential key names

**Symptom**: `network.unifi` test (wave 3) failed with "UniFi credentials not found in secrets YAML".

**Root cause**: `verify-unifi-networking/tasks/capture-config-fact.yaml` checked for
`_unifi_secrets.username` and `_unifi_secrets.password`, but the actual secrets YAML stores
credentials as `_provider_unifi_username` and `_provider_unifi_password`.

**Fix**: Updated both `capture-config-fact.yaml` (validation check) and
`playbook.verify-unifi-networking.yaml` (environment variables) to use the correct key names.

### 2. power-mgmt-test: Duplicate machines from examples path

**Symptom**: Wave 6 (`external.power`) test reported each physical machine twice.

**Root cause**: `_tg_providers.maas.config_params` is a flat dict that includes BOTH the
actual machine entries (at `pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/*`) AND
the example entries (at `maas-pkg/_stack/maas/examples/pwy-homelab/machines/*`). The
example parent path has `_skip_on_build: true` set, but this is NOT automatically inherited
by child entries when iterating the flat `config_params` dict.

The playbook filtered by `power_type in physical_types and not skip` but did not check
the `_skip_on_build` inheritance.

**Fix** (proper, not a path hack): Added ancestor chain traversal in all three affected
playbooks to check if any ancestor path has `_skip_on_build: true` before including a
machine. This mirrors how Terragrunt's `ancestor_merge` works but implemented inline in
Jinja2 using `_all_config_params`.

Files fixed:
- `maas-pkg/_wave_scripts/test-ansible-playbooks/power-mgmt/power-mgmt-test/playbook.yaml`
- `maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-machines-precheck/playbook.yaml`
- `maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-machines-test/playbook.yaml`

### 3. maas wave test playbooks: Missing ansible.cfg (pipelining + remote_tmp)

**Symptom**: `power-mgmt-test` (and potentially other maas test playbooks that SSH to
maas-server-1) failed with `dd: failed to open '...'` due to Ansible computing a relative
remote temp path.

**Root cause**: The maas `test-ansible-playbooks` had no `ansible.cfg`. Without
`pipelining = true` and `remote_tmp = /tmp/.ansible`, Ansible uses dd to transfer module
files and computes a relative path that fails.

**Fix**: Created `maas-pkg/_wave_scripts/test-ansible-playbooks/ansible.cfg` with
`pipelining = true`, `remote_tmp = /tmp/.ansible`, SSH retry settings, and no-ControlMaster
settings. Updated the run scripts for `power-mgmt-test`, `maas-server-seed-test`,
`maas-machines-precheck`, and `maas-machines-test` to set
`ANSIBLE_CONFIG="$(dirname "$(dirname "$SCRIPT_DIR")")/ansible.cfg"`.

### 4. configure-server: Increase SSH connection retries

**Symptom**: `configure-server` playbook intermittently fails with "Broken pipe" during
the `fix-maas-amt-ssl.yaml` or other task sections, even when MaaS is already installed
(mostly no-ops). The pipe breaks ~3 minutes into the run.

**Root cause**: MaaS's `dhcp_probe_service` runs every ~3 minutes and probes all
interfaces including the management NIC (eth0). The probe briefly disrupts TCP connections.
With `ControlMaster=no`, each task opens a fresh SSH connection, and if that connection
attempt coincides with the probe disruption, it fails.

**Fix**: Added `retries = 15` to `[ssh_connection]` in both
`configure-server/ansible.cfg` and `test-ansible-playbooks/ansible.cfg`. Ansible retries
each SSH connection attempt up to 15 times (~5s between retries = ~75s retry window),
which is enough to wait out the 20-second DHCP probe disruption.

## Files Changed

- `infra/unifi-pkg/_wave_scripts/common/verify-unifi-networking/tasks/capture-config-fact.yaml`
- `infra/unifi-pkg/_wave_scripts/common/verify-unifi-networking/playbook.verify-unifi-networking.yaml`
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/power-mgmt/power-mgmt-test/playbook.yaml`
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/power-mgmt/power-mgmt-test/run`
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-machines-precheck/playbook.yaml`
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-machines-precheck/run`
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-machines-test/playbook.yaml`
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-machines-test/run`
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-server-seed-test/run`
- `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/ansible.cfg` (new file)
- `infra/maas-pkg/_tg_scripts/maas/configure-server/ansible.cfg`
