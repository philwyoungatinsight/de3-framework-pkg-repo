# Plan: Standardize `examples-archive` Across Individual Package Repos

## Objective

Create a consistent `examples-archive` directory in every provider package repo (all
except `pwy-home-lab-pkg-repo`, `de3-framework-pkg-repo`, and `de3-gui-pkg-repo`) that
holds real working example units with `_skip_on_build: true` so they are excluded from
`./run --apply` by default. Currently most repos have empty `examples/` gitkeep
placeholders with no content and no `_skip_on_build` config; mikrotik has a real example
(`example-lab`) but uses a different naming convention; GCP has all its units as examples
but with no dedicated subdirectory. This plan standardises the naming, adds `_skip_on_build`
config, and populates examples for every package using real units copied from
`pwy-home-lab-pkg` (with deployment-specific values replaced by example placeholders).

---

## Context

### Current state per repo

| Repo | Provider(s) | Current example state |
|------|-------------|----------------------|
| `de3-aws-pkg-repo` | aws | `aws-pkg/_stack/aws/examples/` — `.gitkeep` only, no `_skip_on_build` in config |
| `de3-azure-pkg-repo` | azure | `azure-pkg/_stack/azure/examples/` — `.gitkeep` only, no `_skip_on_build` |
| `de3-gcp-pkg-repo` | gcp | ALL units under `gcp-pkg/_stack/gcp/` are examples; `_skip_on_build: true` at the top `gcp-pkg/_stack/gcp:` ancestor. No `examples-archive` subdir |
| `de3-image-maker-pkg-repo` | proxmox | `image-maker-pkg/_stack/proxmox/examples/` — `.gitkeep` only |
| `de3-maas-pkg-repo` | maas + null | `maas-pkg/_stack/maas/examples/` and `_stack/null/examples/` — `.gitkeep` only |
| `de3-mesh-central-pkg-repo` | proxmox + null | `mesh-central-pkg/_stack/null/examples/` — `.gitkeep` only. Config references `mesh-central-pkg/_stack/proxmox/example-lab/...` but that directory doesn't exist! |
| `de3-mikrotik-pkg-repo` | routeros | `mikrotik-pkg/_stack/routeros/example-lab/` — FULL real example (`terragrunt.hcl`) with `_skip_on_build: true` in config. Just uses wrong directory name (`example-lab` instead of `examples-archive`) |
| `de3-proxmox-pkg-repo` | proxmox + null | `proxmox-pkg/_stack/proxmox/examples/` and `_stack/null/examples/` — `.gitkeep` only |
| `de3-unifi-pkg-repo` | unifi | `unifi-pkg/_stack/unifi/examples/` — `.gitkeep` only |

### Standard pattern (from mikrotik, the most complete)

```yaml
# In <pkg>.yaml config_params:
<pkg>/_stack/<provider>/examples-archive:
  _env: example
  _provider: <provider>
  _skip_on_build: true
  _region: example-lab

<pkg>/_stack/<provider>/examples-archive/example-lab/<resource-path>:
  _unit_purpose: >
    Example <resource>. Copy to your deployment package and replace with real values.
  _wave: <wave-name>
  # ... resource-specific params with placeholder values
```

### `_skip_on_build` evaluatability requirement

**Critical**: Any unit subtree marked `_skip_on_build: true` MUST still provide all
config values required for `try()` fallbacks to evaluate without crashing. Terragrunt
evaluates ALL unit `locals` during dependency-graph discovery BEFORE the exclude block
fires. Minimum required dummy values: `_env: example`, `_region: example-lab`,
`project_prefix: example` (cloud pkgs), and any provider endpoint param.

### Note on `_skip_on_build` direction

> ⚠️ **Correction needed**: The user's description said "set `_skip_on_build: false` so
> it will not be run" — but that is backwards. `_skip_on_build: true` excludes a unit
> from `./run --apply`; `_skip_on_build: false` (the default) includes it. This plan
> uses `_skip_on_build: true` at the `examples-archive` ancestor, matching the existing
> mikrotik and GCP patterns. See Open Question 1.

---

## Open Questions

1. **`_skip_on_build: true`** — examples excluded from `./run --apply` by default. ✓

2. **GCP restructure** — keep existing unit dirs in place (all already have `_skip_on_build: true`
   at the `gcp-pkg/_stack/gcp:` ancestor). Just add `examples-archive/.gitkeep` alongside
   the existing units. No directory renames needed. ✓

3. **Old `examples/` dirs** — remove (git rm), but only after verifying no content is lost.
   All current `examples/` dirs contain only `.gitkeep` except mikrotik which is being moved.
   Safe to remove. ✓

4. **Mikrotik rename** — `routeros/example-lab/` → `routeros/examples-archive/example-lab/`
   via `git mv`. Config path `mikrotik-pkg/_stack/routeros/example-lab:` split into
   `examples-archive:` (parent with `_skip_on_build: true`) and `examples-archive/example-lab:`
   (child with region/endpoint params). ✓

5. **Examples are fully runnable** — each example must contain enough config to be
   **copied into a new deployment repo (like pwy-home-lab-pkg) and run after filling in
   credentials/IPs**. Each package already declares its dependencies in `framework_packages.yaml`
   (`_requires_capability`), so the example assumes those dependent packages are present.
   Config values should be realistic (based on pwy-home-lab-pkg structure) with `example-lab`
   naming and placeholder IPs/MACs/credentials clearly marked. ✓

6. **Framework docs** — update `skip-parameters.md` to use `examples-archive` naming. ✓

---

## Files to Create / Modify

Changes are grouped by repo. Each repo is committed separately.

---

### `de3-aws-pkg-repo`

#### `infra/aws-pkg/_config/aws-pkg.yaml` — modify

Add `config_params` block after `seed:`:

```yaml
aws-pkg:
  _provides_capability:
  - aws-pkg: "1.0.0"
  seed: ...

  config_params:
    aws-pkg/_stack/aws/examples-archive:
      _env: example
      _provider: aws
      _skip_on_build: true
      _region: us-east-1
      project_prefix: example

    aws-pkg/_stack/aws/examples-archive/example-lab/us-east-1/dev/test-bucket:
      _unit_purpose: >
        Example S3 bucket. Copy to your deployment package (e.g. pwy-home-lab-pkg)
        and set real values. Bucket name defaults to <project_prefix>-test-bucket.
      _wave: cloud.storage
      force_destroy: true
      versioning_enabled: true

    aws-pkg/_stack/aws/examples-archive/example-lab/us-east-1/dev/test-bucket/all-config:
      _unit_purpose: >
        Example S3 object — uploads the merged stack config JSON to the bucket above.
      _wave: cloud.storage
```

#### `infra/aws-pkg/_stack/aws/examples-archive/` — create

- Remove `infra/aws-pkg/_stack/aws/examples/.gitkeep` (git rm)
- Add `infra/aws-pkg/_stack/aws/examples-archive/.gitkeep`
- Add `infra/aws-pkg/_stack/aws/examples-archive/example-lab/us-east-1/dev/test-bucket/terragrunt.hcl` — copy from `pwy-home-lab-pkg/_stack/aws/us-east-1/dev/test-bucket/terragrunt.hcl` (file is config-driven, no deployment-specific values)
- Add `infra/aws-pkg/_stack/aws/examples-archive/example-lab/us-east-1/dev/test-bucket/all-config/terragrunt.hcl` — copy from `pwy-home-lab-pkg/_stack/aws/us-east-1/dev/test-bucket/all-config/terragrunt.hcl`

---

### `de3-azure-pkg-repo`

#### `infra/azure-pkg/_config/azure-pkg.yaml` — modify

Add `config_params` block:

```yaml
  config_params:
    azure-pkg/_stack/azure/examples-archive:
      _env: example
      _provider: azure
      _skip_on_build: true
      _region: eastus
      project_prefix: example

    azure-pkg/_stack/azure/examples-archive/example-lab/eastus/dev/buckets/test-bucket:
      _unit_purpose: >
        Example Azure Blob Storage container. Copy to your deployment package
        and set real subscription_id, resource_group, etc. via seed config.
      _wave: cloud.storage
      force_destroy: true
```

#### `infra/azure-pkg/_stack/azure/examples-archive/` — create

- `git rm infra/azure-pkg/_stack/azure/examples/.gitkeep`
- Add `infra/azure-pkg/_stack/azure/examples-archive/.gitkeep`
- Add `infra/azure-pkg/_stack/azure/examples-archive/example-lab/eastus/dev/buckets/test-bucket/terragrunt.hcl` — copy from `pwy-home-lab-pkg/_stack/azure/eastus/dev/buckets/test-bucket-hmc-a/terragrunt.hcl`

---

### `de3-gcp-pkg-repo`

**Two options** (depends on answer to Open Question 2):

**Option A — Restructure** (preferred): Move existing unit dirs under `examples-archive/example-lab/`:
- `gcp/_stack/gcp/us-central1/dev/test-bucket/` → `gcp/_stack/gcp/examples-archive/example-lab/us-central1/dev/test-bucket/`
- `gcp/_stack/gcp/us-central1/dev/test-bucket-3/` → `gcp/_stack/gcp/examples-archive/example-lab/us-central1/dev/test-bucket-3/`
- `gcp/_stack/gcp/us-central1/dev/clusters/gke-cluster-dev/` → `gcp/_stack/gcp/examples-archive/example-lab/us-central1/dev/clusters/gke-cluster-dev/`
- Update `gcp-pkg.yaml` config_params paths from `gcp-pkg/_stack/gcp:` to `gcp-pkg/_stack/gcp/examples-archive:`, and all child paths accordingly

**Option B — Keep existing, add examples-archive alongside** (less invasive):
- Keep existing `gcp/_stack/gcp/us-central1/...` units in place (already `_skip_on_build: true`)
- Add `gcp/_stack/gcp/examples-archive/.gitkeep` (no unit dirs yet — units are already examples)
- Just rename the ancestor config key from `gcp-pkg/_stack/gcp:` to include the comment
  that all units are examples. No functional change.

Recommend Option A for long-term cleanliness.

---

### `de3-image-maker-pkg-repo`

#### `infra/image-maker-pkg/_config/image-maker-pkg.yaml` — modify

Add `config_params`:

```yaml
  config_params:
    image-maker-pkg/_stack/proxmox/examples-archive:
      _env: example
      _provider: proxmox
      _skip_on_build: true
      _region: example-lab
      _provider_proxmox_endpoint: https://10.0.10.115:8006
      node_name: pve-1
      project_prefix: example

    image-maker-pkg/_stack/proxmox/examples-archive/example-lab/pve-nodes/pve-1/vms/utils/image-maker:
      _unit_purpose: >
        Example image-maker VM on pve-1. Creates Ubuntu 24.04 VM, installs Packer
        and Kairos tooling, then builds VM templates. Copy to your deployment package
        and set real Proxmox endpoint, credentials, and node config.
      _wave: vms.proxmox.custom-images.image-maker
      cpu_cores: 4
      disk_size: 100
      memory_mb: 8192
      # ... full VM params — see pwy-home-lab-pkg for reference values
```

#### `infra/image-maker-pkg/_stack/proxmox/examples-archive/` — create

- `git rm infra/image-maker-pkg/_stack/proxmox/examples/.gitkeep`
- Add `infra/image-maker-pkg/_stack/proxmox/examples-archive/.gitkeep`
- Add `infra/image-maker-pkg/_stack/proxmox/examples-archive/example-lab/pve-nodes/pve-1/vms/utils/image-maker/terragrunt.hcl` — copy from `pwy-home-lab-pkg/_stack/proxmox/pwy-homelab/pve-nodes/pve-1/vms/utils/image-maker/terragrunt.hcl` (or equivalent in image-maker-pkg if it exists)

---

### `de3-maas-pkg-repo`

Two providers: `maas` and `null`.

#### `infra/maas-pkg/_config/maas-pkg.yaml` — modify

Add `config_params` for both providers' examples-archive ancestors plus representative units:

```yaml
  config_params:
    # --- null provider examples ---
    maas-pkg/_stack/null/examples-archive:
      _env: example
      _provider: null
      _skip_on_build: true
      _region: example-lab

    maas-pkg/_stack/null/examples-archive/example-lab/maas/configure-region:
      _unit_purpose: >
        Example: install and configure the MaaS region controller. Copy to your
        deployment package. Requires a Proxmox VM as the target host.
      _wave: <wave-name>
      maas_server: 10.0.10.11   # replace with your MaaS server IP
      # ... other region params

    # --- maas provider examples ---
    maas-pkg/_stack/maas/examples-archive:
      _env: example
      _provider: maas
      _skip_on_build: true
      _region: example-lab
      maas_api_url: http://10.0.10.11:5240/MAAS   # replace with real
      project_prefix: example

    maas-pkg/_stack/maas/examples-archive/example-lab/machines/example-machine-1:
      _unit_purpose: >
        Example physical machine enrolled in MaaS. Shows the full lifecycle config
        (machine → commission → ready → allocated → deploying → deployed).
        Copy to your deployment package and set real power params.
      _wave: maas.lifecycle.new
      power_type: amt
      amt_address: 10.0.11.10   # replace with real AMT IP
      amt_port: 16993
      osystem: ubuntu
      distro_series: noble
```

#### `infra/maas-pkg/_stack/` — create

For the `null` provider:
- `git rm infra/maas-pkg/_stack/null/examples/.gitkeep`
- Add `infra/maas-pkg/_stack/null/examples-archive/.gitkeep`
- Add `infra/maas-pkg/_stack/null/examples-archive/example-lab/maas/configure-region/terragrunt.hcl` — copy from `pwy-home-lab-pkg/_stack/null/pwy-homelab/maas/configure-region/terragrunt.hcl`

For the `maas` provider:
- `git rm infra/maas-pkg/_stack/maas/examples/.gitkeep`
- Add `infra/maas-pkg/_stack/maas/examples-archive/.gitkeep`
- Add the full MaaS lifecycle directory tree for one example machine (copied from `pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/pxe-test-vm-1/...`):
  - `examples-archive/example-lab/machines/example-machine-1/terragrunt.hcl`
  - `examples-archive/example-lab/machines/example-machine-1/commission/terragrunt.hcl`
  - `examples-archive/example-lab/machines/example-machine-1/commission/ready/terragrunt.hcl`
  - `examples-archive/example-lab/machines/example-machine-1/commission/ready/allocated/terragrunt.hcl`
  - `examples-archive/example-lab/machines/example-machine-1/commission/ready/allocated/deploying/terragrunt.hcl`
  - `examples-archive/example-lab/machines/example-machine-1/commission/ready/allocated/deploying/deployed/terragrunt.hcl`

---

### `de3-mesh-central-pkg-repo`

Currently has a config_params entry pointing to a non-existent directory:
`mesh-central-pkg/_stack/proxmox/example-lab/pve-nodes/pve-1/vms/utils/mesh-central`

This needs to be fixed — either create the directory, or update the config path to match
the new naming convention.

#### `infra/mesh-central-pkg/_config/mesh-central-pkg.yaml` — modify

Add `_skip_on_build: true` at the ancestor level and fix the path to match `examples-archive`:

```yaml
  config_params:
    mesh-central-pkg/_stack/proxmox/examples-archive:
      _env: example
      _provider: proxmox
      _skip_on_build: true
      _region: example-lab
      _provider_proxmox_endpoint: https://10.0.10.115:8006
      node_name: pve-1
      project_prefix: example

    mesh-central-pkg/_stack/proxmox/examples-archive/example-lab/pve-nodes/pve-1/vms/utils/mesh-central:
      # (move existing entry here, unchanged)
      _unit_purpose: MeshCentral server VM on pve-1 ...
      _provider: proxmox
      ...
```

Also remove (or rename) the existing orphaned `null/examples/` gitkeep:
- `git rm infra/mesh-central-pkg/_stack/null/examples/.gitkeep`
- Add `infra/mesh-central-pkg/_stack/null/examples-archive/.gitkeep`
- Optionally: add a `null` provider example for the ansible configure-server step if applicable

#### `infra/mesh-central-pkg/_stack/proxmox/examples-archive/` — create

- Add `infra/mesh-central-pkg/_stack/proxmox/examples-archive/.gitkeep`
- Add `infra/mesh-central-pkg/_stack/proxmox/examples-archive/example-lab/pve-nodes/pve-1/vms/utils/mesh-central/terragrunt.hcl` — source from `pwy-home-lab-pkg`'s mesh-central VM unit

---

### `de3-mikrotik-pkg-repo`

Has the most complete example — just needs the directory renamed.

#### `infra/mikrotik-pkg/_config/mikrotik-pkg.yaml` — modify

Update config_params keys:
- `mikrotik-pkg/_stack/routeros/example-lab:` → `mikrotik-pkg/_stack/routeros/examples-archive:`
- `mikrotik-pkg/_stack/routeros/example-lab/switches/crs317-example-switch:` → `mikrotik-pkg/_stack/routeros/examples-archive/example-lab/switches/crs317-example-switch:`

The `_region: example-lab` param that was at the old ancestor path should now live
at `mikrotik-pkg/_stack/routeros/examples-archive/example-lab:` as a child of the
new `examples-archive` ancestor (which sets `_skip_on_build: true`).

Updated structure:
```yaml
  config_params:
    mikrotik-pkg/_stack/routeros/examples-archive:
      _env: example
      _provider: routeros
      _skip_on_build: true

    mikrotik-pkg/_stack/routeros/examples-archive/example-lab:
      _region: example-lab
      _provider_routeros_endpoint: "apis://192.168.88.1:8729"
      _provider_routeros_insecure: true

    mikrotik-pkg/_stack/routeros/examples-archive/example-lab/switches/crs317-example-switch:
      # (existing params unchanged)
```

#### `infra/mikrotik-pkg/_stack/routeros/` — restructure

- `git mv infra/mikrotik-pkg/_stack/routeros/example-lab infra/mikrotik-pkg/_stack/routeros/examples-archive/example-lab`
  (moves the full tree including the `switches/crs317-example-switch/terragrunt.hcl`)

---

### `de3-proxmox-pkg-repo`

Two providers: `proxmox` and `null`.

#### `infra/proxmox-pkg/_config/proxmox-pkg.yaml` — modify

Add `config_params`:

```yaml
  config_params:
    # --- proxmox provider examples ---
    proxmox-pkg/_stack/proxmox/examples-archive:
      _env: example
      _provider: proxmox
      _skip_on_build: true
      _region: example-lab
      _provider_proxmox_endpoint: https://10.0.10.115:8006
      node_name: pve-1
      project_prefix: example

    proxmox-pkg/_stack/proxmox/examples-archive/example-lab/pve-nodes/pve-1/isos/ubuntu-24:
      _unit_purpose: >
        Example: download Ubuntu 24.04 cloud image ISO to Proxmox local storage.
        Copy to your deployment package and set real node_name and endpoint.
      _wave: external.proxmox.isos-and-snippets

    proxmox-pkg/_stack/proxmox/examples-archive/example-lab/pve-nodes/pve-1/vms/test/test-ubuntu-vm-1:
      _unit_purpose: >
        Example Ubuntu 24.04 cloud image VM on pve-1. Boots with cloud-init.
        Copy to your deployment package and set real Proxmox endpoint and credentials.
      _wave: vms.proxmox.from-web.ubuntu
      cpu_cores: 2
      disk_size: 20
      memory_mb: 2048
      vm_id: 1001

    # --- null provider examples ---
    proxmox-pkg/_stack/null/examples-archive:
      _env: example
      _provider: null
      _skip_on_build: true
      _region: example-lab

    proxmox-pkg/_stack/null/examples-archive/example-lab/proxmox/install-proxmox:
      _unit_purpose: >
        Example: install Proxmox VE on a freshly-deployed Debian host.
      _wave: hypervisor.proxmox.install
```

#### `infra/proxmox-pkg/_stack/` — create

For `proxmox` provider:
- `git rm infra/proxmox-pkg/_stack/proxmox/examples/.gitkeep`
- Add `infra/proxmox-pkg/_stack/proxmox/examples-archive/.gitkeep`
- Add `infra/proxmox-pkg/_stack/proxmox/examples-archive/example-lab/pve-nodes/pve-1/isos/ubuntu-24/terragrunt.hcl` — copy from `pwy-home-lab-pkg/_stack/proxmox/pwy-homelab/pve-nodes/pve-1/isos/ubuntu-24/terragrunt.hcl`
- Add `infra/proxmox-pkg/_stack/proxmox/examples-archive/example-lab/pve-nodes/pve-1/vms/test/test-ubuntu-vm-1/terragrunt.hcl` — copy from `pwy-home-lab-pkg/_stack/proxmox/pwy-homelab/pve-nodes/pve-1/vms/test/test-ubuntu-vm-1/terragrunt.hcl`

For `null` provider:
- `git rm infra/proxmox-pkg/_stack/null/examples/.gitkeep`
- Add `infra/proxmox-pkg/_stack/null/examples-archive/.gitkeep`
- Add `infra/proxmox-pkg/_stack/null/examples-archive/example-lab/proxmox/install-proxmox/terragrunt.hcl` — copy from `pwy-home-lab-pkg/_stack/null/pwy-homelab/proxmox/install-proxmox/terragrunt.hcl`

---

### `de3-unifi-pkg-repo`

#### `infra/unifi-pkg/_config/unifi-pkg.yaml` — modify

Add `config_params`:

```yaml
  config_params:
    unifi-pkg/_stack/unifi/examples-archive:
      _env: example
      _provider: unifi
      _skip_on_build: true
      _region: example-lab
      _provider_unifi_api_url: https://192.168.2.1
      _provider_unifi_insecure: true
      project_prefix: example
      domain_name: homelab.local

    unifi-pkg/_stack/unifi/examples-archive/example-lab/port-profile:
      _unit_purpose: >
        Example UniFi port profiles: hypervisor_trunk, amt_mgmt, pxe_provisioning,
        and public_only. Copy to your deployment package and adjust VLAN assignments.
      _wave: network.unifi

    unifi-pkg/_stack/unifi/examples-archive/example-lab/network:
      _unit_purpose: >
        Example UniFi VLAN definitions: cloud_public (10), management (11),
        provisioning (12), guest (13), storage (14). Copy and set real VLAN IDs
        and subnets.
      _wave: network.unifi
      vlans:
        cloud_public:
          dhcp_enabled: true
          dhcp_start: 10.0.10.100
          dhcp_stop: 10.0.10.254
          name: Cloud-Public
          purpose: corporate
          subnet: 10.0.10.0/24
          vlan_id: 10
        # ... other VLANs

    unifi-pkg/_stack/unifi/examples-archive/example-lab/device:
      _unit_purpose: >
        Example UniFi device port assignments. Shows how to map MACs to port profiles
        for a USW-Flex-2.5G-8 and UDM. Replace MAC addresses and port numbers with
        your real values.
      _wave: network.unifi
      devices:
        switch_flex:
          mac: "aa:bb:cc:dd:ee:ff"   # replace with real MAC
          name: USW-Flex-2.5G-8
          type: switch
          port_overrides:
            "1":
              name: host-1-port
              port_profile: hypervisor_trunk
        udm:
          mac: "aa:bb:cc:dd:ee:00"   # replace with real MAC
          name: UniFi Dream Machine
          type: gateway
```

#### `infra/unifi-pkg/_stack/unifi/examples-archive/` — create

- `git rm infra/unifi-pkg/_stack/unifi/examples/.gitkeep`
- Add `infra/unifi-pkg/_stack/unifi/examples-archive/.gitkeep`
- Add `infra/unifi-pkg/_stack/unifi/examples-archive/example-lab/port-profile/terragrunt.hcl` — copy from `pwy-home-lab-pkg/_stack/unifi/pwy-homelab/port-profile/terragrunt.hcl`
- Add `infra/unifi-pkg/_stack/unifi/examples-archive/example-lab/network/terragrunt.hcl` — copy from `pwy-home-lab-pkg/_stack/unifi/pwy-homelab/network/terragrunt.hcl`
- Add `infra/unifi-pkg/_stack/unifi/examples-archive/example-lab/device/terragrunt.hcl` — copy from `pwy-home-lab-pkg/_stack/unifi/pwy-homelab/device/terragrunt.hcl`

---

### `de3-framework-pkg-repo` (conditional on Open Question 6)

#### `infra/_framework-pkg/_docs/framework/skip-parameters.md` — modify

Update the example code block that currently shows `examples/` to use `examples-archive/`:

```yaml
# Before:
<pkg>/_stack/<provider>/examples:
  _skip_on_build: true

# After:
<pkg>/_stack/<provider>/examples-archive:
  _env: example
  _provider: <provider>
  _skip_on_build: true
  _region: example-lab
```

Also update the prose to describe `examples-archive` as the standard naming convention.

---

## Execution Order

1. **Answer open questions** — particularly Q1 (`_skip_on_build` direction) and Q2 (GCP restructure strategy) before touching GCP.

2. **`de3-mikrotik-pkg-repo`** — simplest case: `git mv` the existing `example-lab` tree and update two config_params keys. Low risk, establishes pattern for others.

3. **`de3-unifi-pkg-repo`** — second: add example with real content from pwy-home-lab-pkg. Provider has no complex cross-dependencies.

4. **`de3-aws-pkg-repo`** and **`de3-azure-pkg-repo`** — in parallel. Both are simple bucket examples with no cross-repo dependencies.

5. **`de3-gcp-pkg-repo`** — depends on Q2 decision. If Option A, restructure dirs first, then update config.

6. **`de3-proxmox-pkg-repo`** — add examples for VM and null provider. Some units have `_proxmox_deps.hcl` includes that must remain valid.

7. **`de3-maas-pkg-repo`** — most complex due to full lifecycle directory tree. Copy all 6 lifecycle stages from pwy-home-lab-pkg.

8. **`de3-mesh-central-pkg-repo`** — fix the broken orphaned config_params, create the matching directory, move existing config to `examples-archive` path.

9. **`de3-image-maker-pkg-repo`** — add proxmox VM example.

10. **`de3-framework-pkg-repo`** (optional, Q6) — update skip-parameters.md.

11. **Verify** — run `./run -A de3-gui` to confirm the GUI sees the example units with `_skip_on_build: true` rendered correctly. Run `./run -l` to confirm no wave listing errors.

---

## Verification

After all repos are updated:

```bash
# 1. Confirm examples-archive units are excluded from build in each repo
./run -l 2>&1 | grep -v "skip"      # no example units should appear in wave listing

# 2. Check that the GUI renders examples-archive nodes with the correct skip badge
./run -A de3-gui

# 3. Spot-check _skip_on_build is set in each package config
grep -rn "_skip_on_build" \
  /home/pyoung/git/de3-ext-packages/de3-aws-pkg-repo/main/infra/aws-pkg/_config/ \
  /home/pyoung/git/de3-ext-packages/de3-unifi-pkg-repo/main/infra/unifi-pkg/_config/ \
  /home/pyoung/git/de3-ext-packages/de3-mikrotik-pkg-repo/main/infra/mikrotik-pkg/_config/ \
  | grep "examples-archive"

# 4. Confirm no orphaned config_params paths (paths with no matching directory)
# Spot-check mesh-central: verify the proxmox/examples-archive dir now exists
ls /home/pyoung/git/de3-ext-packages/de3-mesh-central-pkg-repo/main/infra/mesh-central-pkg/_stack/proxmox/examples-archive/

# 5. Confirm old empty 'examples/' dirs are gone
find /home/pyoung/git/de3-ext-packages -name "examples" -type d 2>/dev/null
# should return empty (all renamed to examples-archive)
```
