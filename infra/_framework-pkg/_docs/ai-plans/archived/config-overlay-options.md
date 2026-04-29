# Config Overlay — Design Plan

**Problem:** External packages (`proxmox-pkg`, `maas-pkg`, etc.) ship with config under `<pkg>/_config/<pkg>.yaml`. When imported via symlink, that config is read-only — it lives in the external repo. The deployment repo (`pwy-home-lab-pkg`) needs to set or override deployment-specific values (IPs, credentials, environment names) for units that live in those imported packages, with no current mechanism to do so.

**Chosen approach:** Per-package `config_source` declaration in `framework_packages.yaml`. Each imported package independently declares which local package owns its deployment config. Multiple imported packages can declare different config sources, or the same one.

---

## Config consumers and how they find config

There are 11 config consumers. They split into two categories:

**Path-derived (hard-coded lookup):** These construct the config file path from the unit's directory path. They are the only consumers affected by this change.

| Consumer | How it derives config path |
|---|---|
| `root.hcl` | `infra/${p_package}/_config/${p_package}.yaml` — one file per unit evaluation |
| `unit-mgr/config_yaml.py` | `infra/<pkg>/_config/<pkg>.yaml` from first path component of unit path |

**Glob-based (auto-discovery):** These load ALL `infra/*/_config/*.yaml` files and aggregate `config_params` from all of them into a single flat dict. They are indifferent to which file a given key comes from — a `proxmox-pkg/_stack/...` key in `pwy-home-lab-pkg.yaml` is handled identically to the same key in `proxmox-pkg.yaml`.

| Consumer | Discovery method |
|---|---|
| `generate_ansible_inventory.py` | `glob("infra/*/_config/*.yaml")` |
| `config_base` Ansible role | `find infra/ -maxdepth 3 -path '*/_config/*.yaml'` |
| `validate-config.py` | `glob("infra/*/_config/*.yaml")` |
| `./run` | glob + `framework_config.py` |
| `framework-utils.sh` | `_find_component_config()` |

**Glob-based consumers require no changes** — they pick up cross-package config_params keys automatically. Only root.hcl and unit-mgr need updating.

---

## Chosen design: per-package `config_source`

### Declaration

Each imported package in `framework_packages.yaml` gains an optional `config_source` field naming the local package that owns its deployment config. Packages without `config_source` own their own config as today.

```yaml
# infra/default-pkg/_config/framework_packages.yaml
framework_packages:
  - name: proxmox-pkg
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: proxmox-pkg
    config_source: pwy-home-lab-pkg     # ← deployment config for proxmox units lives here

  - name: maas-pkg
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: maas-pkg
    config_source: pwy-home-lab-pkg     # ← can point to the same package

  - name: unifi-pkg
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: unifi-pkg
    config_source: pwy-home-lab-pkg

  - name: pwy-home-lab-pkg
    public: false
    # no config_source — owns its own config

  - name: default-pkg
    public: true
    # no config_source — framework package, owns its own config
```

Different packages can declare different `config_source` values. If a repo hosts two independent deployment packages (e.g., `lab-pkg` and `staging-pkg`), each imported package can point to whichever is appropriate. There is no global default — omitting `config_source` always means "own package."

### Config file layout

The config_source package holds `config_params` entries keyed with the imported package's path prefix. No new YAML structure — same `config_params` map as today, just with keys from other packages.

```yaml
# infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml
pwy-home-lab-pkg:
  config_params:
    # This package's own units
    pwy-home-lab-pkg/_stack/null/pwy-homelab/all-config: {}

    # Deployment config for imported packages (keyed with their path prefix)
    proxmox-pkg/_stack/proxmox/pwy-homelab:
      _provider: proxmox
      endpoint: https://10.0.10.20:8006
    proxmox-pkg/_stack/proxmox/pwy-homelab/pve-nodes/pve-1:
      ansible_host: 10.0.10.20

    maas-pkg/_stack/maas/pwy-homelab/server:
      api_endpoint: http://10.0.10.11:5240/MAAS

    unifi-pkg/_stack/unifi/pwy-homelab:
      controller_url: https://10.0.10.1
```

Secrets follow the same pattern in `pwy-home-lab-pkg_secrets.sops.yaml`:

```yaml
pwy-home-lab-pkg_secrets:
  config_params:
    proxmox-pkg/_stack/proxmox/pwy-homelab:
      api_token: secret-value
    maas-pkg/_stack/maas/pwy-homelab/server:
      api_key: secret-value
```

### Merge semantics

When loading a unit at `proxmox-pkg/_stack/...`, config-mgr (and root.hcl during the transition) loads config from **two sources** and merges them:

1. The package's own YAML (`proxmox-pkg.yaml`) — structural defaults: `_provider`, `_wave`, `_skip_on_build`, module paths, etc.
2. The config_source package YAML (`pwy-home-lab-pkg.yaml`) — deployment values: IPs, credentials, environment-specific settings.

The config_source wins on any conflict. The ancestor-merge algorithm is applied across the combined key set.

Loading both is important: source packages ship structural defaults that should not need to be duplicated in every deployment's config_source file.

### How tools resolve a unit's config

The lookup is always: `framework_packages.yaml` → find the entry for `<pkg>` → check `config_source`.

1. No `config_source` → config is in `infra/<pkg>/_config/<pkg>.yaml` only (existing behaviour)
2. `config_source: X` → config is merged from `infra/<pkg>/_config/<pkg>.yaml` (structural) AND `infra/X/_config/X.yaml` (deployment overrides)

`framework_packages.yaml` is the single authoritative index. No inference, no filesystem inspection.

---

## Consumer impact

| Consumer | Change needed |
|---|---|
| `root.hcl` | Read merged config from `$_CONFIG_DIR/<pkg>.yaml` and `$_CONFIG_DIR/<pkg>.secrets.yaml` (plain YAML, no SOPS); remove `sops_decrypt_file()` calls; use `get_env("_CONFIG_DIR")` — errors if unset |
| `unit-mgr` | Add `_read_framework_packages()` helper; resolve `config_source` chain; write to config_source YAML instead of unit's own YAML when `config_source` is set |
| `validate-config.py` | Add `config_source` chain validation: existence check + cycle detection |
| `generate_ansible_inventory.py` | Change glob from `infra/*/_config/*.yaml` to `$_CONFIG_DIR/*.yaml` |
| `config_base` Ansible role | Change `find infra/*/_config/` to `find $_CONFIG_DIR/` |
| `./run`, `framework-utils.sh`, others | **No change** |
| `set_env.sh` | Add `_CONFIG_DIR` export; add `mkdir -p "$_CONFIG_DIR"`; call `config-mgr generate` in startup checks |
| `sync-maas-api-key` tg-script | Replace `sops --set` call with `config-mgr set --sops` |

---

## config-mgr with pre-processed dynamic dir

config-mgr is a new tool (`infra/default-pkg/_framework/_config-mgr/`) that centralises all config routing, merging, and SOPS handling. It is the single place where the `config_source` routing logic lives — root.hcl and unit-mgr are updated once to delegate to it, and any future routing changes only touch config-mgr.

### Read path: pre-processed dynamic dir

config-mgr runs as a pre-step and writes pre-merged, pre-decrypted config to `$_DYNAMIC_DIR/config/`. Consumers read plain YAML from there — no SOPS tooling required in any consumer.

```
_DYNAMIC_DIR = infra/default-pkg/_config/tmp/dynamic/    (already gitignored)

_DYNAMIC_DIR/config/
  proxmox-pkg.yaml          ← merged public config (own + config_source overlay, plain YAML)
  proxmox-pkg.secrets.yaml  ← merged secrets (decrypted, mode 600)
  maas-pkg.yaml
  maas-pkg.secrets.yaml
  pwy-home-lab-pkg.yaml
  pwy-home-lab-pkg.secrets.yaml
  ...
  .manifest                 ← mtime fingerprint of all source files (stale detection)
```

For each package with a `config_source`, the output file already contains the merged result — consumers see one authoritative file per package, not two.

**Updated consumer model (post config-mgr):**

| Consumer | Today | With config-mgr + dynamic dir |
|---|---|---|
| `root.hcl` | `yamldecode(file("infra/<pkg>/_config/<pkg>.yaml"))` + `sops_decrypt_file(...)` | `yamldecode(file("$_DYNAMIC_DIR/config/<pkg>.yaml"))` + `yamldecode(file("$_DYNAMIC_DIR/config/<pkg>.secrets.yaml"))` — no SOPS |
| `config_base` Ansible role | `find infra/*/_config/` + `community.sops.load_vars` | `include_vars` from `_DYNAMIC_DIR/config/*.yaml` — no SOPS |
| `generate_ansible_inventory.py` | `glob("infra/*/_config/*.yaml")` | `glob("$_DYNAMIC_DIR/config/*.yaml")` |
| `validate-config.py` | Direct glob of source files | Still reads source files (validates structure, not merged output) |
| `unit-mgr` | Direct `ruamel.yaml` read/write of source files | Still writes to source files; triggers config-mgr regenerate after |

### Write path

Two valid patterns:

1. **Direct file edit** (human, `sops` CLI) → call `config-mgr generate` afterward to refresh the dynamic dir. Dynamic dir is stale until that call.

2. **Via `config-mgr set`** (all automation) → config-mgr writes to the correct source file (routing via `config_source`) AND regenerates the dynamic dir in one call. Callers don't need to know file paths, SOPS invocation, or routing rules.

All automation that currently writes config files must migrate to `config-mgr set`. The canonical example is `sync-maas-api-key`, which calls `sops --set` directly — this becomes `config-mgr set --sops`.

### Build ordering and performance

`config-mgr generate` is called from `set_env.sh` on every shell source. It is fast and silent:

- Compares source file mtimes against `.manifest`; skips unchanged packages
- No output when everything is up to date
- One line per regenerated package (e.g., `config-mgr: regenerated proxmox-pkg`)
- Errors to stderr, exit non-zero

On any SOPS error (key unavailable, decryption failure, malformed file): exit immediately with a clear error, leave no partial output, do not update the manifest. The dynamic dir retains its last-good state. Failures propagate to the calling shell and stop dependent work.

### CLI surface

```
config-mgr generate
  # Pre-process all source config → _DYNAMIC_DIR/config/
  # Skips unchanged packages via mtime manifest.

config-mgr get <unit-path>
  # Print merged config_params for one unit (reads dynamic dir, applies ancestor-merge).

config-mgr set <unit-path> <key> <value> [--sops]
  # Write a config_params key to the correct source file (routing via config_source).
  # --sops writes to the SOPS secrets file.
  # Re-runs generate after write.

config-mgr set-raw <pkg> <yaml-key-path> <value> [--sops]
  # Write an arbitrary key in a package's config (not scoped to config_params).
  # For non-config_params fields: _provides_capability, vars, etc.
  # Re-runs generate after write.

config-mgr move <src-unit-path> <dst-unit-path>
  # Rename config_params keys (delegates from unit-mgr).
  # Re-runs generate after write.
```

---

## Implementation phases

### Phase 1 — `config_source` declaration
**File:** `infra/default-pkg/_config/framework_packages.yaml`

Add `config_source: <pkg>` to each imported package that needs deployment config overrides. No code changes. This is inert data until config-mgr exists.

---

### Phase 2 — config-mgr tool (new)
**Directory:** `infra/default-pkg/_framework/_config-mgr/`

Structure (mirrors unit-mgr):
```
_config-mgr/
  run                        # bash entry point: sources set_env.sh, activates venv, exec python3 -m config_mgr.main "$@"
  requirements.txt           # pyyaml, ruamel.yaml
  config_mgr/
    __init__.py
    main.py                  # argparse CLI: generate, get, set, set-raw, move subcommands
    packages.py              # read framework_packages.yaml; resolve config_source chains; cycle detection
    merger.py                # merge source + config_source config_params dicts
    generator.py             # generate dynamic dir: mtime manifest, merge, SOPS decrypt, write
    writer.py                # write config_params to correct source file (routing via config_source)
    sops.py                  # SOPS subprocess helpers (decrypt to dict, set key in encrypted file)
```

**`packages.py` — key functions:**
- `load_framework_packages(repo_root)` → list of package dicts from `framework_packages.yaml`
- `resolve_config_source(pkg_name, packages)` → follows chain `pkg → config_source → config_source_of_config_source → ...`; returns the terminal package name; raises on cycle or missing package

**`generator.py` — `generate(repo_root, config_dir, output_mode)` logic:**
1. Load `framework_packages.yaml`; load `framework_config_mgr.yaml` for `merge_method` and `output_mode`
2. Load mtime manifest from `$_CONFIG_DIR/.manifest` (JSON: `{pkg: {filepath: mtime, ...}, ...}`)
3. For each package:
   a. Collect source files: own YAML, own SOPS secrets, config_source YAML, config_source SOPS secrets (following chain)
   b. If all source file mtimes match manifest → skip (print nothing for silent/normal modes)
   c. Load own YAML public config_params and config_source public config_params
   d. Merge: `combined = {**own_config_params, **config_source_config_params}` (config_source wins)
   e. Write merged public YAML to `$_CONFIG_DIR/<pkg>.yaml` — preserving top-level key structure (`{pkg_name: {config_params: combined, ...other keys...}}`)
   f. Decrypt own SOPS secrets + config_source SOPS secrets (subprocess `sops --decrypt`)
   g. Merge secrets config_params same way; write to `$_CONFIG_DIR/<pkg>.secrets.yaml` (mode 600) — preserving `<pkg>_secrets` top-level key
   h. Update manifest entry for this package
4. Write manifest atomically
5. On any SOPS error: print error to stderr, exit non-zero, do NOT update manifest

**`writer.py` — `set_config_param(unit_path, key, value, sops, repo_root)` logic:**
1. Derive pkg from first component of unit_path
2. Resolve config_source for that pkg
3. Target file = `infra/<config_source>/_config/<config_source>.yaml` (or `.sops.yaml` with `--sops`)
4. Write using ruamel.yaml (same as unit-mgr's config_yaml.py) or `sops --set` for SOPS file
5. Call `generate()` to refresh dynamic dir

**Mtime manifest format** (`$_CONFIG_DIR/.manifest`, JSON):
```json
{
  "proxmox-pkg": {
    "infra/proxmox-pkg/_config/proxmox-pkg.yaml": 1234567890.1,
    "infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml": 1234567892.3
  }
}
```

---

### Phase 3 — `set_env.sh`
**File:** `set_env.sh`

In `_set_env_export_vars`: add `export _CONFIG_DIR="$_DYNAMIC_DIR/config"`

In `_set_env_create_dirs`: add `"$_CONFIG_DIR"` to the `mkdir -p` call.

In `_set_env_run_startup_checks`: call config-mgr generate before validate-config. Config-mgr errors must block (no `|| true`) — a SOPS failure here should stop the shell source.

**Circular-source problem:** config-mgr's `run` script sources `set_env.sh`, which would cause infinite recursion if set_env.sh calls `run`. Solution: set_env.sh calls the Python module directly, bypassing the `run` wrapper. config-mgr must therefore work with the system python3 (same as validate-config.py today). Add a sibling entry point `_config-mgr/generate` that activates the venv if present, then calls `python3 -m config_mgr.main generate` — set_env.sh calls this script.

```bash
# in _set_env_run_startup_checks, before the validate-config block:
"$_FRAMEWORK_DIR/_config-mgr/generate" >&2
```

`_config-mgr/generate` is a minimal bash script: activate venv if present, then `exec python3 -m config_mgr.main generate`. It does NOT source `set_env.sh`.

---

### Phase 4 — `validate-config.py`
**File:** `infra/default-pkg/_framework/_utilities/python/validate-config.py`

Add new validation rule after existing rules:

**RULE 6 — config_source chain validation:**
- Load `framework_packages.yaml`
- For each package with `config_source`:
  - Verify the named package exists in `framework_packages.yaml`; error if not
  - Follow the chain using DFS; if any package is visited twice, error with the full cycle path listed (e.g., `cycle detected: a-pkg → b-pkg → a-pkg`)

---

### Phase 5 — `root.hcl`
**File:** `infra/default-pkg/_framework/_git_root/root.hcl`

Replace direct source-file loading with dynamic dir reads. config-mgr has already merged config_source into the output files, so root.hcl needs no routing logic — it just reads the pre-merged file.

```hcl
# Before:
_package_cfg_file = "${local.stack_root}/infra/${local.p_package}/_config/${local.p_package}.yaml"
_package_cfg_raw  = yamldecode(file(local._package_cfg_file))

_pkg_sec_path  = "${local.stack_root}/infra/${local.p_package}/_config/${local.p_package}_secrets.sops.yaml"
_package_sec   = fileexists(local._pkg_sec_path) ? yamldecode(sops_decrypt_file(local._pkg_sec_path)) : {}

_fw_sec_path   = "${local.stack_root}/infra/default-pkg/_config/framework_secrets.sops.yaml"
_framework_sec = fileexists(local._fw_sec_path) ? yamldecode(sops_decrypt_file(local._fw_sec_path)) : {}

# After:
_config_dir = get_env("_CONFIG_DIR")   # errors if unset — correct; set_env.sh must be sourced first

_package_cfg_file = "${local._config_dir}/${local.p_package}.yaml"
_package_cfg_raw  = yamldecode(file(local._package_cfg_file))   # errors if file missing — correct

_pkg_sec_path  = "${local._config_dir}/${local.p_package}.secrets.yaml"
_package_sec   = fileexists(local._pkg_sec_path) ? yamldecode(file(local._pkg_sec_path)) : {}
# top-level key structure is preserved by config-mgr; existing try() logic unchanged

_fw_sec_path   = "${local._config_dir}/default-pkg.secrets.yaml"
_framework_sec = fileexists(local._fw_sec_path) ? yamldecode(file(local._fw_sec_path)) : {}
```

No `sops_decrypt_file()` calls remain. The `_package_sec_cfg` and `_framework_sec_cfg` try() fallback logic is unchanged — config-mgr preserves the `<pkg>_secrets` top-level key in its output.

---

### Phase 6 — `unit-mgr`
**File:** `infra/default-pkg/_framework/_unit-mgr/unit_mgr/main.py` and `config_yaml.py`

Add to `main.py`:
```python
def _read_framework_packages(repo_root: Path) -> list[dict]:
    import os as _os
    pkg_dir = _os.environ.get("_DEFAULT_PKG_DIR") or str(repo_root / "infra" / "default-pkg")
    path = Path(pkg_dir) / "_config" / "framework_packages.yaml"
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("framework_packages", [])

def _resolve_config_source(pkg_name: str, packages: list[dict]) -> str:
    """Follow config_source chain; return terminal package name. Raises on cycle."""
    pkg_map = {p["name"]: p for p in packages}
    visited, current = [], pkg_name
    while True:
        if current in visited:
            raise ValueError(f"config_source cycle: {' → '.join(visited + [current])}")
        visited.append(current)
        entry = pkg_map.get(current, {})
        nxt = entry.get("config_source")
        if not nxt:
            return current
        current = nxt
```

In `main.py` where `src_yaml_path` is constructed, call `_resolve_config_source(src_pkg, packages)` to get the actual file to read/write. Pass the resolved path to `migrate_config_params` instead of the original package path.

---

### Phase 7 — glob consumer migration
**Files:** `generate_ansible_inventory.py`, `config_base` Ansible role

`generate_ansible_inventory.py`: replace `glob("infra/*/_config/*.yaml")` with `glob(os.environ["_CONFIG_DIR"] + "/*.yaml")`. Error if `_CONFIG_DIR` not set.

`config_base/tasks/main.yaml`: replace `find "{{ common_infra_dir }}" -maxdepth 3 -path '*/_config/*.yaml'` with `find "{{ lookup('env', '_CONFIG_DIR') }}" -maxdepth 1 -name '*.yaml'`. Error if `_CONFIG_DIR` is empty.

Both consumers now read pre-merged, pre-decrypted files — `community.sops.load_vars` and the sops glob filter in config_base can be removed.

---

### Phase 8 — config writer migration

**Scan results — two categories of writes found:**

**A. `sops --set` writes (in de3-runner external packages)**

These are in Ansible tasks inside external package tg-scripts. All write API keys/tokens that are generated at provision time (not known ahead of time and therefore cannot be in the source YAML at deploy time).

| File (relative to `_ext_packages/de3-runner/main/`) | What it writes | Key path |
|---|---|---|
| `infra/maas-pkg/_tg_scripts/maas/sync-api-key/playbook.yaml` | MaaS admin API key (sync on 401) | `maas-pkg_secrets.config_params.<path>._provider_maas_api_key` |
| `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/install-maas.yaml` | MaaS admin API key (initial install) | `maas-pkg_secrets.config_params.<path>._provider_maas_api_key` |
| `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/install-maas.yaml` | MaaS admin API key (server variant) | same |
| `infra/proxmox-pkg/_tg_scripts/proxmox/configure/tasks/configure-api-token.yaml` | Proxmox API token id + secret | `proxmox-pkg_secrets.providers.proxmox.config_params.<path>.token.{id,secret}` (old nested format) |

Each of these must be migrated to call `config-mgr set --sops` instead of `sops --set`. This requires changes to the **de3-runner repo** — not the local deployment repo. These changes must be coordinated with or submitted as a PR to de3-runner.

Note: the Proxmox tg-script uses the old nested `providers.proxmox.config_params` format; after migration it should use the flat `config_params` format to match current convention.

**B. Direct Python reads of source `_config/` files**

These scripts read config files by absolute path rather than receiving values via Terragrunt config_params. They need to read from `$_CONFIG_DIR/<pkg>.yaml` instead.

| File (relative to `_ext_packages/de3-runner/main/`) | Reads | What it reads |
|---|---|---|
| `infra/maas-pkg/_wave_scripts/common/fetch-maas-state/run` | `maas-pkg.yaml` via `$_MAAS_CONFIG` | `vars.maas_server` hostname |
| `infra/de3-gui-pkg/_application/de3-gui/run` | `de3-gui-pkg.yaml` via `_read_config()` | `config.vm_ip`, `config.websocket_port` |
| `infra/pwy-home-lab-pkg/_tg_scripts/local/update-ssh-config/run` | `pwy-home-lab-pkg.yaml` | `ssh_config.dynamic_config_path` |

Each must be updated to read from `$_CONFIG_DIR/<pkg>.yaml` (already decrypted and merged). The first two are in de3-runner; the third is in the local `pwy-home-lab-pkg` tg-scripts (check if it lives in the local repo or is also symlinked from de3-runner).

**C. `filesha256()` in terragrunt.hcl files**

Several `terragrunt.hcl` units use `filesha256()` on source config files to force re-apply when config changes. These should **keep pointing to source files** — the dynamic dir is a derived cache and its mtime is not a reliable signal for config changes. No changes needed here.

**D. Local pkg-mgr writes**

After any pkg-mgr command that writes a config file, call `config-mgr generate` to refresh `$_CONFIG_DIR`. Commands: `add-repo`, `remove-repo`, `import`, `remove`, `rename`, `copy`.

```bash
# at end of each write-capable command in pkg-mgr/run:
"$SCRIPT_DIR/../_config-mgr/generate"
```

**Two-repo scope:** Phases 1–7 are entirely within the local `pwy-home-lab-pkg` repo (changes to `infra/default-pkg/`). Phase 8A and 8B (external tg-scripts and wave scripts) require changes to the **de3-runner repo**. These must land in de3-runner before the external packages will fully work with config-mgr. de3-runner also has its own `infra/default-pkg/` copy; if de3-runner is used standalone (outside a deployment repo), that copy will also need the same framework changes — this is a separate de3-runner PR that mirrors the framework changes.

---

## config-mgr configuration file

`infra/default-pkg/_config/framework_config_mgr.yaml` — created. Documents and controls config-mgr behaviour. Key parameters:

- **`merge_method`** (default: `interleave`) — how source package and config_source package config_params are combined. Two methods:
  - `interleave`: both participate in ancestor-merge; config_source wins at the same path depth. Structural defaults in the source package remain effective without duplication.
  - `source_only`: only config_source config_params are used; source package config_params ignored entirely. Use after a full migration of a package's config into the deployment repo.
- **`output_mode`** (default: `normal`) — controls verbosity during `generate`. `normal` prints only regenerated packages; `silent` suppresses all non-error output; `verbose` prints every package including skipped.

`merge_method` can also be overridden per-package in `framework_packages.yaml` via a `config_merge_method` field, allowing different strategies for different packages without changing the global default.

---

## Decided

- **Chosen approach:** Option A variant — per-package `config_source` in `framework_packages.yaml`. No global deployment_package key; each package declares its own source independently.
- **Merge semantics:** `interleave` by default — both source package (structural defaults) and config_source package (deployment overrides) participate in ancestor-merge; config_source wins at same depth.
- **`_CONFIG_DIR` env var:** `set_env.sh` exports `_CONFIG_DIR="$_DYNAMIC_DIR/config"` alongside the other `_DYNAMIC_DIR` children (`_EPHEMERAL_DIR`, `_WAVE_LOGS_DIR`, `_GUI_DIR`). All consumers that read from the dynamic config dir reference `$_CONFIG_DIR/<pkg>.yaml` — no hardcoded paths.
- **`config-mgr generate` in `set_env.sh`:** Called on every source. Fast and silent via mtime manifest. One line per regenerated package. Errors to stderr, exit non-zero.
- **SOPS errors:** Hard stop. Exit immediately, no partial output, manifest not updated.
- **unit-mgr same-file move confirmed:** When `src_yaml_path == dst_yaml_path` (both resolve to the config_source file), unit-mgr's cross-package branch correctly handles this — it operates on different top-level keys (`src_pkg` section vs `dst_pkg` section), saves atomically after each step, and the second load picks up the first save. No code change needed for this case beyond adding the config_source routing.
- **config_source chaining is valid:** A package can declare `config_source: X` where X itself declares `config_source: Y`. This allows layered deployment patterns (e.g., source package → base deployment layer → final deployment package). Circular chains must be detected and rejected by validate-config.py.
- **Merge implementation:** `combined = {**source_config_params, **config_source_config_params}` — config_source unconditionally overwrites source package on any key conflict. The combined dict is then passed to the standard ancestor-merge algorithm. No ambiguity; no ordering concern.
- **validate-config.py cycle detection:** Follow each `config_source` chain to its end. If any package is visited twice, reject with a clear error listing the cycle. Also validate that every `config_source` value names a package present in `framework_packages.yaml`.

## Open questions

None.
