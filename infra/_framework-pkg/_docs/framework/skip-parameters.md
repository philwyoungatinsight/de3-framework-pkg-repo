# Skip Parameters

How to control which units and waves are excluded from build and clean operations.

---

## Overview

There are two levels of skip control:

| Level | Where it lives | Who reads it |
|-------|----------------|--------------|
| Wave-level | `waves:` block in `<pkg>.yaml` | `run` Python orchestrator |
| Unit-level | `config_params:` in `<pkg>.yaml` | `root.hcl` (Terragrunt) |

`make clean-all` **ignores all skip parameters unconditionally.** It exists specifically to destroy everything — no skipping, no exceptions.

---

## Wave-level skip (in `waves:`)

```yaml
<pkg>:
  waves:
  - name: network.unifi
    _skip_on_wave_run: true     # skip this wave during both "make" (build) and "make clean"
```

| Parameter | Effect |
|-----------|--------|
| `_skip_on_wave_run: true` | Wave is skipped during `make` (build) AND `make clean` (reverse destroy). Has **no effect** on `make clean-all`. Targeting the wave explicitly with `-w` overrides it and forces execution. |

Use this for waves that are expensive or slow to rebuild and should survive normal build and clean cycles (e.g. cloud storage buckets, network config, Proxmox ISOs).

The `waves_ordering.yaml` file is the authoritative source of which waves carry `_skip_on_wave_run`. Per-package `<pkg>.yaml` files must also set `_skip_on_wave_run: true` on the matching wave definition so that the `run` orchestrator applies the skip when reading merged wave data.

**This is the only supported mechanism for preserving resources across `make` and `make clean`.**

---

## Unit-level skip (in `config_params:`)

These are set as keys inside a `config_params:` path entry.

Set `_skip_on_build: true` at an ancestor path; all child units inherit the value via ancestor-merge. Override with `_skip_on_build: false` at a child path to re-enable a specific subtree.

```yaml
<pkg>:
  config_params:
    <pkg>/_stack/<provider>/examples:
      _skip_on_build: true    # all units under examples/ are skipped on build
```

| Parameter | Inherits? | Excludes from | Use case |
|-----------|-----------|---------------|----------|
| `_skip_on_build: true` | Yes | `apply`, `plan`, `validate`, `output`, `state` | Example trees shipped with a package but not deployed by default. Set once at the ancestor `examples/` path. Override with `_skip_on_build: false` at a child path to re-enable a specific subtree. |

---

## `make clean-all` ignores all skips

`make clean-all` (`./run --clean-all`) destroys every managed resource:
- Sets `_FORCE_DELETE=YES` in the environment before running Terraform.
- `root.hcl` reads `_FORCE_DELETE` and disables the `exclude` block entirely, so `_skip_on_build` units are destroyed like any other unit.
- Wave `_skip_on_wave_run` flags are ignored — `skip_patterns` is empty so no wave is skipped by the orchestrator.
- After destroy, the GCS state bucket is wiped completely.

Use `make clean-all` when you need a fully clean slate. Use `make clean` when you want to preserve resources in waves marked `_skip_on_wave_run`.

---

## Example: example tree that ships with a package

```yaml
proxmox-pkg:
  config_params:
    proxmox-pkg/_stack/proxmox/examples:
      _provider: proxmox
      _skip_on_build: true       # entire examples/ subtree skipped by default
    proxmox-pkg/_stack/proxmox/examples/pwy-homelab:
      env: dev
      region: pwy-homelab
      # inherits _skip_on_build: true — not deployed
    proxmox-pkg/_stack/proxmox/examples/pwy-homelab/pve-nodes/pve-1:
      _skip_on_build: false      # override: this specific subtree IS deployed
      node_name: pve
```

## Example: preserve network config across build and clean cycles

```yaml
unifi-pkg:
  waves:
  - name: network.unifi
    _skip_on_wave_run: true         # wave skipped during both "make" and "make clean"
```

---

## Summary table

| Parameter | Scope | Inherits | Skips on build | Skips on clean | Ignored by clean-all |
|-----------|-------|----------|----------------|----------------|----------------------|
| Wave `_skip_on_wave_run` | Wave | N/A | Yes | Yes | Yes |
| `_skip_on_build` | Unit (config_params) | Yes | Yes | No | Yes |
