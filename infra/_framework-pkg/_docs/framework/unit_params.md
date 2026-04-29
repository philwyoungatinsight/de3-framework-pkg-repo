# Unit Params — Reserved Keys

- `unit_params` is the merged config map available to every Terragrunt unit via
`include.root.locals.unit_params`.
- Values are sourced from per-package `<pkg>.yaml` under `config_params:`
using ancestor-path merging (deeper paths win over parents).

Most keys are provider-specific (e.g. `disk_size`, `memory_mb` for Proxmox
VMs). The keys documented here are **reserved framework keys** — they are read
by `root.hcl` itself and affect Terragrunt behaviour across all unit types.

**Naming rule:** all reserved framework keys start with `_`. Keys without a
leading underscore are treated as pass-through values for module inputs only.

---

## Reserved Keys

### `_wave`

**Type:** string (e.g. `maas.server`, `vms.proxmox.utility.mesh-central`)
**Default:** none (unit always runs — not wave-filtered)

Controls which execution wave this unit belongs to. Used with the `TG_WAVE`
environment variable to selectively include units during
`terragrunt run --all apply`. Set at any ancestor path level; child paths
inherit via ancestor-merge.

```yaml
"unifi-pkg/_stack/unifi/pwy-homelab":
  _wave: network.unifi   # inherited by network, port-profile, device sub-units

"pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-01":
  _wave: maas.machines
```

**Wave semantics:**

| `TG_WAVE` value | Behaviour |
|-----------------|-----------|
| *(unset)* | All units run — `_wave` is ignored |
| `<name>` | Only units with `_wave: <name>` run; all others skipped |
| `<name1>,<name2>` | Units whose `_wave` is in the comma-separated list run |
| `all` | All units run (same as unset) |

Units with **no `_wave`** always run regardless of `TG_WAVE`. These are
"foundation" units (backend, etc.) that every wave depends on.

**Note on glob patterns:** `TG_WAVE` itself only supports exact names and
comma-separated lists. The `./run -w PATTERN` CLI flag applies `fnmatch` glob
matching (e.g. `-w 'vm.*'`) in Python to select which named waves to run —
the `run` script then passes the exact wave name to `TG_WAVE` when invoking
Terragrunt. If you set `TG_WAVE` manually, use exact names only.

The `waves:` list in `config/framework.yaml` defines the ordered set of
waves the `run` script processes. See
[waves.md](waves.md) for the full wave system.

---

### `_modules_dir`

**Type:** string (path relative to `infra/`)  
**Default:** resolved automatically by `root.hcl` (3-tier fallback)  
**Inheritance:** Yes

Overrides the module directory used by this unit. By default `root.hcl`
resolves `modules_dir` via a 3-tier fallback:

1. `infra/<p_package>/_modules/` — if a `.modules-root` sentinel file is present
2. `infra/<provider>-pkg/_modules/` — canonical provider package
3. `infra/_framework-pkg/_modules/` — always present (null/utility modules)

`_modules_dir` bypasses all three tiers and points directly to a specific
directory. Use it when a deployment package (e.g. `pwy-home-lab-pkg`) needs to
reference modules that live in another package:

```yaml
"pwy-home-lab-pkg/_stack/null/pwy-homelab":
  _modules_dir: _framework-pkg/_modules   # relative to infra/
```

**Note:** `p_package` (which controls config loading and state paths) is
always derived from the unit's filesystem path — the first segment after
`infra/`. It cannot be overridden via a config_params key.

---

### `_tg_scripts_dir` / `_wave_scripts_dir`

**Type:** string (path relative to `infra/`)  
**Default:** `<p_package>/_tg_scripts` / `<p_package>/_wave_scripts`  
**Inheritance:** Yes

Override the directories where `root.hcl` looks for Terragrunt hook scripts
and wave test/precheck playbooks respectively. The default derives both from
`p_package` (the first path segment after `infra/`).

Use when a deployment package (e.g. `pwy-home-lab-pkg`) hosts units that
should run scripts owned by a different canonical package:

```yaml
"pwy-home-lab-pkg/_stack/proxmox/pwy-homelab":
  _tg_scripts_dir:   proxmox-pkg/_tg_scripts    # relative to infra/
  _wave_scripts_dir: proxmox-pkg/_wave_scripts
```

---

### `_skip_on_build`

**Type:** bool  
**Default:** `false`  
**Inheritance:** Yes — set at an ancestor path, all descendants inherit it.

Excludes the unit from build operations (`apply`, `plan`, `validate`, `output`, `state`). Used to ship example unit trees with a package without deploying them by default. Set at the top-level `examples/` ancestor path; all children inherit automatically.

Override with `_skip_on_build: false` at a child path to re-enable a specific subtree.

```yaml
<pkg>:
  config_params:
    <pkg>/_stack/<provider>/examples:
      _skip_on_build: true   # entire examples/ subtree excluded from apply
    <pkg>/_stack/<provider>/examples/my-env/special-unit:
      _skip_on_build: false  # re-enable this subtree specifically
```

**`make clean-all` ignores this flag** — it destroys all resources unconditionally.

---

See [skip-parameters.md](skip-parameters.md) for the full reference.

---

### `_region`

**Type:** string  
**Required:** yes  
**Inheritance:** Yes

Geographic or site region for this unit (e.g. `us-central1`, `pwy-homelab`).
Used in `common_tags` and GCS state path prefixes. Set once at an ancestor path;
all descendants inherit it. `root.hcl` raises a hard error if missing.

---

### `_env`

**Type:** string  
**Required:** yes  
**Inheritance:** Yes

Deployment environment (e.g. `dev`, `prod`). Used in `common_tags`. Same rules as `_region`.

---

### `_maas_server_ip`

**Type:** string  
**Default:** `""`  
**Inheritance:** Yes

IP address of the MaaS server. Read by `root.hcl` and exposed as
`include.root.locals.maas_server_ip` for units that need it (e.g. pxe-test-vm, maas-server).

---

### `_maas_server_cidr_prefix`

**Type:** number  
**Default:** `24`  
**Inheritance:** Yes

CIDR prefix length for the MaaS server's IP. Companion to `_maas_server_ip`.

---

### `_unit_purpose`

**Type:** string  
**Default:** `""`  
**Inheritance:** No — **enforced**. Read directly from the exact `config_params` path for this unit (`local._config_params[local.rel_path]`), not from the ancestor-merged `unit_params`. Setting it at an ancestor path will not propagate to children.  
**Accessible as:** `include.root.locals.unit_purpose`  
**Affects framework behaviour:** No — purely informational

A human-readable description of what this unit does and why it exists. Read by tooling
and humans; has no effect on apply/destroy behaviour.

```yaml
pwy-home-lab-pkg/_stack/null/pwy-homelab/configure-physical-machines:
  _unit_purpose: >-
    Commission and deploy all physical machines via MaaS. Aggregating unit for
    the full machine fleet — downstream units take a single dep here so adding/
    removing a machine requires no change to them.
```

**When to set it:**

| Scope | Set `_unit_purpose` when… |
|-------|----------------------|
| Aggregating/orchestration units | Always — these are otherwise opaque null resources whose role is not obvious from their name |
| Ancestor paths that set a subtree's wave or provider | Useful — e.g. explain why `pve-nodes/pve-1` is `_skip_on_build: false` |
| Individual leaf VMs / machines | When the resource needs justification beyond its name (optional for obvious names like `test-ubuntu-vm-1`) |

**Populating `_unit_purpose` — suggested rollout order:**

1. **Aggregating/orchestration null units** *(done)* — `configure-physical-machines`,
   `install-proxmox`, `wait-for-proxmox`, `configure-proxmox`, `update-mesh-central`,
   `sync-maas-api-key`, `maas/configure-server`, `mesh-central/configure-server`
2. **Ancestor path entries** — paths that set `_wave`, `_provider`, or `_skip_*` for a whole
   subtree: explain what that subtree is and why the flag is set
3. **Utility VMs** — `maas-server-1`, `mesh-central`, `image-maker`, `pxe-test-vm-1`
4. **Leaf VMs and machines** — physical machines (ms01-01 etc.), test VMs; skip if name is self-explanatory

---

### `_managed_by`

**Type:** string  
**Default:** `"terragrunt"`  
**Inheritance:** Yes

Value written to the `managed_by` tag on every resource. Override when a unit
is provisioned by a different tool (e.g. `"ansible"`, `"manual"`) and you want
that reflected in cloud resource tags.

```yaml
"pwy-home-lab-pkg/_stack/null/pwy-homelab":
  _managed_by: ansible   # all null units in this subtree get managed_by=ansible
```

Leave unset in the vast majority of cases — `"terragrunt"` is the correct value
for anything Terraform manages.

---

### `_cost_center` / `_owner` / `_application`

**Type:** string  
**Default:** `""`  
**Inheritance:** Yes

Optional metadata added to `common_tags` on every resource. Not used by any
framework logic — purely informational tag values.

---

### `additional_tags`

**Type:** list of strings
**Default:** `[]`

Extra tags applied to the resource (VM, machine, etc.) at creation time.
Tags of the form `role_<name>` are the primary mechanism for assigning hosts
to **Ansible inventory groups**: the inventory generator
(`generate_ansible_inventory.py`) strips the `role_` prefix and places the
host in a group named `<name>`.

```yaml
"pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-01":
  additional_tags:
    - role_mgmt_group_ms01   # → Ansible group: mgmt_group_ms01
    - role_proxmox_server    # → Ansible group: proxmox_server
```

Playbooks then target those groups:

```yaml
- name: Install Proxmox
  hosts: proxmox_server
```

**Current `role_*` tags and their groups:**

| Tag | Ansible group | Used by |
|-----|--------------|---------|
| `role_maas_server` | `maas_server` | configure-maas, configure-machines, wave tests |
| `role_mesh_central` | `mesh_central` | install/update-mesh-central |
| `role_image_maker` | `image_maker` | build-images, vms-image-maker-test |
| `role_proxmox_server` | `proxmox_server` | install-proxmox, proxmox-install-precheck |
| `role_mgmt_group_ms01` | `mgmt_group_ms01` | update-mesh-central (`mgmt_group_*` wildcard) |
| `role_mgmt_group_nuc` | `mgmt_group_nuc` | update-mesh-central (`mgmt_group_*` wildcard) |

Non-`role_` tags (e.g. `wipe-host-clean`) are applied to the resource but
create no Ansible group. They may be read by scripts that iterate
`additional_tags` directly.

The `pve_hosts` Ansible group is **not** driven by `additional_tags` — it is
built by the inventory generator from all `pve-nodes/<node>` paths in the
proxmox config_params.

---

### `_extra_providers`

**Type:** list of strings  
**Default:** `[]`  
**Inheritance:** No — set on the exact unit that needs the extra provider.

Declares additional Terraform provider plugins required by a unit beyond its primary provider. The most common case is a unit whose primary provider is (e.g.) `gcp` but which also uses a `null_resource` — it must declare `_extra_providers: ["null"]`.

```yaml
pwy-home-lab-pkg/_stack/gcp/us-central1/dev/clusters/gke-cluster-dev/kubeconfig:
  _extra_providers:
  - 'null'   # quotes required — bare null is a YAML reserved word
```

**How it works:** `root.hcl` reads the list, resolves an `.entry.tpl` fragment for each name using the same 3-tier lookup as the primary provider template, then splices the entries into the `required_providers {}` block of the generated provider file.

**3-tier lookup order for `<name>.entry.tpl`:**

1. `infra/<current-package>/_providers/<name>.entry.tpl`
2. `infra/<name>-pkg/_providers/<name>.entry.tpl`
3. `infra/_framework-pkg/_providers/<name>.entry.tpl` *(fallback)*

The `null` provider entry fragment lives at `infra/_framework-pkg/_providers/null.entry.tpl`.

**YAML quoting:** YAML reserved words (`null`, `true`, `false`) must be quoted when used as list values, otherwise `yamldecode` in HCL receives a null instead of a string.

---

## Provider-Specific Prefix Convention

Keys starting with `_provider_` are also reserved — they override the
corresponding provider connection parameter for that unit:

| Key | Overrides |
|-----|-----------|
| `_provider_endpoint` | Provider API endpoint URL |
| `_provider_insecure` | TLS verification skip |
| `_provider_ssh_username` | SSH username for provider |
| `_provider_ssh_agent` | Use SSH agent for provider auth |
| `_provider_api_url` | API URL (for providers that use URL not endpoint) |

These are documented further in `root.hcl` under the "Template-based
providers" section.
