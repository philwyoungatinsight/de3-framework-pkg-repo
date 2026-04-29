# Framework Architecture

Describes the framework itself — how the pieces fit together — not what resources it manages.

---

## Execution Pipeline

`make build` → Python orchestrator → ordered waves → per-wave Terragrunt + Ansible steps.

```mermaid
flowchart TD
    make["make build / clean-all"] --> run

    subgraph run["./run  (Python orchestrator)"]
        direction TB
        load["reads infra/_framework-pkg/_config/_framework-pkg.yaml\nextracts ordered waves list"]
        loop["for each wave in order ↓"]
        load --> loop
    end

    loop --> wave_steps

    subgraph wave_steps["Per-Wave Steps  (repeated for every wave)"]
        direction LR
        tg["① terragrunt\nrun --all apply\nTG_WAVE=name"] --> inv["② generate\nansible-inventory"] --> pre["③ pre_ansible_playbook\noptional configure-*"] --> test["④ test_ansible_playbook\noptional wave test"]
    end

    tg --> |"skips units where\n_wave ≠ TG_WAVE"| units

    subgraph units["infra/<pkg>/_stack/  (leaf units)"]
        u1["<pkg-a>/_stack/proxmox/.../vm"]
        u2["<pkg-b>/_stack/maas/.../machine"]
        u3["<pkg-b>/_stack/null/.../playbook"]
    end

    units --> root["root.hcl\nshared config framework"]
    root --> mod["infra/<pkg>/_modules/<provider>/<module>/\n(Terraform module)"]
    mod --> api["Cloud / On-prem API\n(Proxmox · MaaS · AWS · UniFi · …)"]
    mod --> backend["GCS shared backend\n(single state store)"]
```

**Logs:** every run writes to `~/.run-waves-logs/<timestamp>/` — `run.log` (full) and per-wave `wave-<name>-{apply,test,precheck}.log`.

---

## Config Resolution (YAML → Unit)

Every unit inherits config from its ancestor paths in the YAML, deepest path wins.

```mermaid
flowchart TD
    subgraph config_files["Config Files  (per package)"]
        yaml["infra/<pkg>/_config/<pkg>.yaml\npublic config  (top-level key: <pkg>:)"]
        sops["infra/<pkg>/_config/<pkg>_secrets.sops.yaml\nSOPS-encrypted secrets  (top-level key: <pkg>_secrets:)"]
    end

    yaml --> merge
    sops --> |"sops decrypt\nat plan time"| merge

    subgraph merge["root.hcl  —  ancestor-path merge"]
        direction TB
        note["Unit path: <pkg>/_stack/<provider>/<env>/<cluster>/<node>/vms/<vm-name>
Walk ancestors in YAML config_params, merge in order (deepest wins):
  <pkg>/_stack/<provider>/<env>                     → endpoint, node defaults…
  <pkg>/_stack/<provider>/<env>/<cluster>/<node>    → node_name, datastore…
  <pkg>/_stack/…/<node>/vms/<vm-name>               → vm-specific overrides"]
    end

    merge --> unit_params["unit_params\n(public, merged)"]
    merge --> secret_params["unit_secret_params\n(secrets, merged)"]

    unit_params --> tpl
    secret_params --> tpl

    subgraph tpl["infra/<pkg>/_providers/<provider>.tpl  →  provider block"]
        note2["templatefile() fills ENDPOINT, TOKEN_ID, TOKEN_SECRET, …\nOverrides via _provider_PROVIDER_VAR keys in config_params\n(multiple instances share the same template)"]
    end

    unit_params --> inputs["inputs = { … }\nin unit terragrunt.hcl\n(references local.up = unit_params)"]
    inputs --> vars["variables.tf in _modules/…\n→ resource arguments"]
```

**Key rule:** Never hard-code values that exist in the YAML. All per-unit values come from `local.up = include.root.locals.unit_params` using `try(local.up.<key>, <safe-default>)`.

---

## Package System

All infrastructure is organized into self-contained packages under `infra/<pkg>/`. Each package owns its modules, provider templates, scripts, config, and stack units.

```mermaid
flowchart LR
    subgraph pkg["infra/<pkg>/"]
        stack["_stack/<provider>/<path>/<unit>/\nterragrunt.hcl"]
        modules["_modules/<provider>/<module>/\nTerraform module"]
        providers["_providers/<provider>.tpl\nprovider block template"]
        tg_scripts["_tg_scripts/<role>/<name>/run\nbefore_hook / after_hook scripts"]
        wave_scripts["_wave_scripts/test-ansible-playbooks/<role>/<name>/\nwave test/pre playbooks"]
        config["_config/<pkg>.yaml\n<pkg>_secrets.sops.yaml"]
    end

    stack --> |"source module"| modules
    stack --> |"templatefile()"| providers
    stack --> |"before_hook / after_hook"| tg_scripts
```

**A unit's package does not have to own the provider or module it uses.** `root.hcl` resolves both via the same 3-tier lookup, falling through to the canonical provider package automatically. Units in one package routinely use provider templates and modules owned by another package, with no explicit configuration needed.

**Provider template lookup (3-tier, automatic):**
1. `infra/<p_package>/_providers/<provider>.tpl` — unit's own package
2. `infra/<provider>-pkg/_providers/<provider>.tpl` — canonical provider package
3. `infra/_framework-pkg/_providers/<provider>.tpl` — last resort (null only)

**Module lookup (3-tier, automatic):**
1. `infra/<p_package>/_modules/` — unit's own package (detected via `.modules-root` sentinel)
2. `infra/<provider>-pkg/_modules/` — canonical provider package
3. `infra/_framework-pkg/_modules/`

**Explicit override** (when the automatic lookup isn't right):
```yaml
# in config_params for the unit or subtree:
_modules_dir: <other-pkg>/_modules    # relative to infra/
_tg_scripts_dir: <other-pkg>/_tg_scripts
_wave_scripts_dir: <other-pkg>/_wave_scripts
```

**`p_package`** is derived by `root.hcl` from the unit's path (`infra/<pkg>/_stack/…`). It defaults to `"_framework-pkg"`.

---

## Wave System

Waves define an ordered build DAG. Each wave name is a value of `_wave:` in `config_params`.

```mermaid
flowchart LR
    subgraph yaml_waves["_framework-pkg.yaml  —  waves_ordering: list"]
        w1["cloud.storage\n(S3, GCS, Azure Blob)"]
        w2["network.unifi\n(VLANs, port profiles)"]
        w3["pxe.maas.server\n(MaaS seed server VM)"]
        w4["pxe.maas.machines\n(physical machines)"]
        wN["hypervisor.proxmox…\nvm.proxmox…\nlocal.updates\n…"]
        w1 --> w2 --> w3 --> w4 --> wN
    end

    subgraph filter["Wave Filter  (in root.hcl)"]
        exclude["exclude block: skip unit if\n_wave != TG_WAVE env var OR _skip_on_build=true\nDisabled entirely when _FORCE_DELETE=YES (make clean-all)"]
    end

    yaml_waves --> filter

    subgraph each_wave["Per-Wave Execution"]
        direction TB
        apply["terragrunt run --all apply\n(units with matching _wave)"]
        inv2["update ansible inventory\n(if update_inventory: true)"]
        pre2["pre_ansible_playbook\n(optional configure step)\nruns before test"]
        test2["test_ansible_playbook\n(verifies the wave)"]
        apply --> inv2 --> pre2 --> test2
    end

    filter --> each_wave
```

**Destroy** runs waves in **reverse order** (`./run --clean`), so dependencies are torn down before their dependents.

---

## Dependency Model

Three distinct mechanisms, each for a different scope.

```mermaid
flowchart TD
    subgraph wave_order["Wave Ordering  (coarse-grained)"]
        wA["Wave A: infrastructure"] --> wB["Wave B: dependent resources\n(entire wave waits for Wave A)"]
    end

    subgraph tg_deps["Terragrunt dependency block  (output passing)"]
        unitA["Unit A\n(produces outputs)"] --> |"dependency { config_path }\nreads outputs.tf values"| unitB["Unit B\n(consumes Unit A outputs)"]
        note1["mock_outputs_allowed_terraform_commands\n= init, validate, plan, apply\nAllows plan before Unit A exists"]
    end

    subgraph tg_deps2["Terragrunt dependencies block  (ordering only)"]
        unitC["Unit C"] --> |"dependencies { paths = […] }\nno output read, just ordering"| unitD["Unit D\n(apply waits for Unit C)"]
    end

    subgraph hooks["Terragrunt before_hook / after_hook"]
        bh["before_hook\n→ infra/<pkg>/_tg_scripts/<role>/<name>/run\nruns before tofu apply"]
        ah["after_hook\n→ runs after tofu apply/destroy"]
    end

    wave_order --> tg_deps
    tg_deps --> tg_deps2
    tg_deps2 --> hooks
```

---

## Directory Layout

```
pwy-home-lab/                       # repo root = stack root
├── root.hcl                        # Shared config: YAML merge, provider template, backend, wave filter
├── run                             # Python orchestrator: waves, apply, inventory, test hooks
├── set_env.sh                      # Exports path vars; source before any terragrunt command
├── Makefile                        # Thin wrapper: build / clean / clean-all / test
│
├── infra/                          # All packages — each is self-contained
│   ├── <pkg>/
│   │   ├── _stack/<provider>/<path>/<unit>/   ← one leaf dir = one unit = one terragrunt.hcl
│   │   ├── _modules/<provider>/<module>/      ← Terraform modules for this package
│   │   ├── _providers/<provider>.tpl          ← provider { } block templates
│   │   ├── _tg_scripts/<role>/<name>/run      ← called by Terragrunt before/after hooks
│   │   ├── _wave_scripts/test-ansible-playbooks/<role>/<name>/  ← wave test/pre playbooks
│   │   ├── _config/<pkg>.yaml                 ← public config  (top-level key: <pkg>:)
│   │   ├── _config/<pkg>_secrets.sops.yaml    ← SOPS secrets  (top-level key: <pkg>_secrets:)
│   │   └── _setup/run                         ← OS-level tool installation
│   │
│   ├── <stack-pkg>/                # Stack units (uses provider templates + modules from other pkgs)
│   ├── <provider>-pkg/             # Provider template + matching Terraform modules
│   ├── <service>-pkg/              # Service-specific VM + configure/update scripts
│   └── _framework-pkg/                # Fallback package: null provider templates + shared modules; setup tooling
│
├── framework/
│   ├── generate-ansible-inventory/ # Reads GCS state → writes dynamic inventory + SSH config
│   ├── clean-all/                  # nuclear destroy: pre-purge Proxmox VMs + wipe GCS state
│   └── lib/
│       └── merge-stack-config.py   # Merges all <pkg>.yaml files into a single resolved config
│
├── scripts/
│   └── ai-only-scripts/            # AI-generated diagnostic / one-off operational scripts
│
├── utilities/
│   └── bash/
│       ├── init.sh
│       ├── framework-utils.sh      # confirm_destructive, wait_for_condition, _find_component_config
│       └── python-utils.sh
│
└── docs/
    ├── ai-log/                     # Timestamped session logs (written before each commit)
    ├── ai-log-summary/             # Compacted log: current-state facts and key decisions
    └── framework/                  # Architecture docs (this file)
```

---

## SOPS + Secrets Flow

```mermaid
flowchart LR
    editor["sops \$SOPS_FILE\n(opens in \$EDITOR)"] --> |"re-encrypts on save"| sops_file

    subgraph sops_file["infra/<pkg>/_config/<pkg>_secrets.sops.yaml"]
        enc["Encrypted with PGP key(s)\n(no encrypted_regex — all values encrypted)\nroot .sops.yaml is the single rule source"]
    end

    sops_file --> |"sops decrypt\nat terragrunt plan/apply time"| root_hcl

    subgraph root_hcl["root.hcl"]
        read["reads public <pkg>.yaml + decrypted secrets\nmerges ancestor paths → unit_secret_params"]
    end

    root_hcl --> tpl2["infra/<pkg>/_providers/<provider>.tpl\nreceives PASSWORD, TOKEN_SECRET,\nACCESS_KEY, CLIENT_SECRET, …"]
```

**Never use `Write`, `Edit`, shell redirect (`>`), or `tee` on `.sops.yaml` files.**

```bash
# Single key update:
sops --set '["<pkg>_secrets"]["providers"]["<p>"]["config_params"]["<path>"]["<key>"] "<val>"' "$SOPS_FILE"

# Interactive full-file edit:
sops "$SOPS_FILE"

# Create from scratch:
cat > /tmp/new.yaml << 'EOF'
<pkg>_secrets:
  key: value
EOF
EDITOR="cp /tmp/new.yaml" sops "$SOPS_FILE"   # uses target path for rule matching
rm /tmp/new.yaml
```
