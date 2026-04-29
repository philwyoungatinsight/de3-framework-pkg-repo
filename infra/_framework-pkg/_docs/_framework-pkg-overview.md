# _framework-pkg

`_framework-pkg` is a framework-level package. It owns no infrastructure of its own — it provides shared modules, provider templates, and setup tooling that all other packages fall back to.

## Roles

### 1. Module fallback (`_modules/`)

`root.hcl` resolves the Terraform module directory for each unit using a three-tier search:

1. The unit's own package `_modules/` (sentinel file `_modules/.modules-root` must be present)
2. The canonical provider package — e.g. `gcp-pkg/_modules/` for `tf_provider: gcp`
3. **`_framework-pkg/_modules/`** — always present, always last resort

Current modules:

| Module | Purpose |
|---|---|
| `null_resource__run-script` | Run a local script via `null_resource` |
| `null_resource__ssh-script` | Run a script on a remote host over SSH via `null_resource` |

These are cross-cutting utilities used by many packages. They live here rather than in any provider package because they depend only on the `null` provider.

#### How the modules work

**`null_resource__run-script`** wraps any `tg-script` directory as a Terraform resource. The unit passes a `script_dir` (absolute path to a directory containing a `run` script) and a `trigger` string. Terraform calls `run --build` on apply and `run --clean` on destroy. The trigger is whatever causes a re-run — typically a hash of config inputs or a dependency resource ID. Without this module, every script-backed unit would need to hand-write the same `null_resource` + `local-exec` + destroy-provisioner boilerplate.

**`null_resource__ssh-script`** uploads a shell script to a remote host and runs it over SSH, then deletes it. The caller passes the script content as a string (so it re-runs automatically when the content changes) plus the target host, SSH user, and an optional bastion/jump host. Host resolution is built in: if no explicit `host` is given, it picks the first usable IPv4 from the Proxmox provider's `ipv4_addresses` output, skipping loopback and link-local addresses. Without this module, every unit that needs to configure a VM post-boot would need to manage the SSH connection, base64 encoding, and host-discovery logic itself.

#### Usage examples

`null_resource__run-script` — wrapping an Ansible tg-script as a DAG node. The trigger is a hash of all config and playbook files so Terraform re-runs the script whenever any of them change:

```hcl
# infra/pwy-home-lab-pkg/_stack/null/pwy-homelab/proxmox/install-proxmox/terragrunt.hcl
terraform {
  source = "${include.root.locals.modules_dir}/null_resource__run-script"
}

locals {
  config_hash = sha256(join("", [for f in concat(local.config_files, local.script_files) : filesha256(f)]))
}

inputs = {
  trigger    = local.config_hash
  script_dir = "${include.root.locals._tg_scripts}/proxmox/install"
}
```

`null_resource__ssh-script` — configuring a VM after boot. The parent VM unit's `ipv4_addresses` output is passed directly; the module resolves the usable IP:

```hcl
# infra/pwy-home-lab-pkg/_stack/proxmox/pwy-homelab/.../test-ubuntu-vm-1/setup-via-ssh/terragrunt.hcl
dependency "vm" {
  config_path = "../"
}

terraform {
  source = "${include.root.locals.modules_dir}/null_resource__ssh-script"
}

inputs = {
  ipv4_addresses = dependency.vm.outputs.ipv4_addresses
  user           = local.user
  script         = include.root.locals.unit_params.setup_script
}
```

### 2. Provider template fallback (`_providers/`)

Same three-tier logic applies to provider configuration templates. `_framework-pkg/_providers/null.tpl` (and `null.entry.tpl`) serve as the fallback for units that use the `null` provider and whose package doesn't define its own template.

### 3. Setup (`_setup/run`)

`_framework-pkg/_setup/run` is executed first by the `run` orchestrator during environment setup. It installs the framework's required tooling: `jq`, `yq`, `uv`, `sops`, `tofu`, `terragrunt`, `kubectl`, `helm`.

## What lives here vs. elsewhere

A module or provider template belongs in `_framework-pkg` only if it is genuinely provider-agnostic (i.e. depends only on `null`) and is used by more than one package. Provider-specific modules belong in the corresponding `<provider>-pkg`.
