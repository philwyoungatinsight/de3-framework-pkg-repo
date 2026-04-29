# Plan: Isolate "pwy" to infra/pwy-home-lab-pkg

## Goal

All code and docs specific to "pwy-home-lab" must live in `infra/pwy-home-lab-pkg`.
Generic code that happens to use "pwy" names must be renamed to generic equivalents
(e.g. `test-lab`, `de3`). Historical ai-log docs are frozen — do not touch them.

---

## Audit Summary

Running `grep -r pwy` outside `infra/pwy-home-lab-pkg/` reveals six categories:

| Category | Action |
|---|---|
| Directory named `test-bucket-pwy-3` inside `infra/gcp-pkg/_stack/` | Rename → `test-bucket-3` |
| Generic code docstrings/comments that say "pwy-home-lab" (set_env, framework, utilities) | Update to "de3" |
| CLAUDE.md references `pwy-home-lab-GUI` | Update to `de3-gui-pkg` |
| Generic package docs with pwy-specific example paths | Update examples to use `example-lab` / `de3` |
| GUI `homelab_gui.py` hardcodes old package paths and default repo path | Fix paths and default |
| Historical ai-log files | **Leave untouched** |

---

## Changes (in execution order)

### 1. `infra/gcp-pkg/_stack/gcp/us-central1/dev/test-bucket-pwy-3/` → `test-bucket-3/`

The live deployment is in `pwy-home-lab-pkg/_stack/gcp/`. The `gcp-pkg` stacks are
example templates only (comment in `gcp-pkg/_config/gcp-pkg.yaml` says so).
The example unit has a pwy-specific name and is an exact duplicate of the live unit.

**Actions:**
- `git mv infra/gcp-pkg/_stack/gcp/us-central1/dev/test-bucket-pwy-3 infra/gcp-pkg/_stack/gcp/us-central1/dev/test-bucket-3`
- In the moved `terragrunt.hcl`, change the comment `bucket_name: pwy-tg-stack-test-data` → `bucket_name: <project_prefix>-test-data-3`
- In `infra/gcp-pkg/_stack/gcp/us-central1/dev/test-bucket/terragrunt.hcl`, same comment fix: `pwy-tg-stack-test-data` → `<project_prefix>-test-data`

### 2. `set_env.sh` — comment on line 2

```
# Set environment variables for the pwy-home-lab stack.
→
# Set environment variables for the de3 stack.
```

### 3. `framework/manage-unit/manage_unit/main.py` — docstrings lines 1 and 86

```
"""manage-unit CLI — move / copy Terragrunt unit trees in the pwy-home-lab framework."""
→
"""manage-unit CLI — move / copy Terragrunt unit trees in the de3 framework."""

description="Move or copy Terragrunt unit trees in the pwy-home-lab framework.",
→
description="Move or copy Terragrunt unit trees in the de3 framework.",
```

### 4. `utilities/ansible/roles/config_base/filter_plugins/lab_config.py` — docstring line 2

```
Ansible filter plugins for pwy-home-lab config_base role.
→
Ansible filter plugins for de3 config_base role.
```

### 5. `utilities/python/validate-config.py` — flag file path line 153

```
flag_file = ".cache/pwy-home-lab/validate-config-last-run"
→
flag_file = ".cache/de3/validate-config-last-run"
```

(This is the default value for `vc.get("flag_file", ...)` — update the fallback string.)

### 6. `CLAUDE.md` — line 133

```
read by `pwy-home-lab-GUI`
→
read by `de3-gui-pkg`
```

### 7. `infra/mikrotik-pkg/_docs/README.md` — example paths

Two places reference `pwy-homelab` in example commands:
- `cd infra/mikrotik-pkg/_stack/routeros/pwy-homelab/switches/crs317-pwy-homelab`
  → `cd infra/mikrotik-pkg/_stack/routeros/example-lab/switches/crs317-example-switch`
- `Edit ... under the 'crs317-pwy-homelab' key.`
  → `Edit ... under the 'crs317-example-switch' key.`

### 8. `infra/maas-pkg/_modules/maas_machine/variables.tf` — variable description comment

```
(e.g. 'pwy-token-2' or 'root@pam!pwy-token-2')
→
(e.g. 'my-token-1' or 'root@pam!my-token-1')
```

### 9. `infra/image-maker-pkg/_tg_scripts/image-maker/build-images/README.md`

```
Token (`root@pam!pwy-token-2`) must have `privsep=0`
→
Token (e.g. `root@pam!my-token-1`) must have `privsep=0`
```

### 10. `infra/unifi-pkg/_wave_scripts/test-ansible-playbooks/network/network-validate-config/README.md`

```
cd ~/git/pwy-home-lab/deploy/tasks/phase-0/terragrunt/lab_stack
→
cd ~/git/de3
```

(The rest of that command will likely need updating too — read the file and fix all `pwy-home-lab` path refs in that README.)

### 11. `infra/maas-pkg/_tg_scripts/maas/configure-plain-hosts/playbook.configure-plain-hosts.yaml` — comment line 33

```
# The parent pwy-homelab config entry carries maas_host
→
# The parent config entry carries maas_host
```

### 12. `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/fix-maas-amt-ssl.yaml` — comment line 32

Remove or replace the inline mention of `pwy-homelab setup` with a generic description.

### 13. `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — four fixes

**13a. Default repo path (line ~50):**
```python
str(Path.home() / "git/pwy-home-lab"),
→
str(Path.home() / "git/de3"),
```

**13b. Description string (line ~10049):**
```python
"and run operations for the pwy-home-lab stack."
→
"and run operations for the de3 lab stack."
```

**13c. Hardcoded Cytoscape demo elements (lines ~350–365):**
These nodes reference `proxmox-pkg/_stack/proxmox/pwy-homelab` and
`unifi-pkg/_stack/unifi/pwy-homelab` — paths that do NOT exist (the stacks
are in `pwy-home-lab-pkg/_stack/proxmox/pwy-homelab` etc.).
Update all demo-element paths to use the correct current package structure:
- `proxmox-pkg/_stack/proxmox/pwy-homelab` → `pwy-home-lab-pkg/_stack/proxmox/pwy-homelab`
- `unifi-pkg/_stack/unifi/pwy-homelab` → `pwy-home-lab-pkg/_stack/unifi/pwy-homelab`

**13d. Hardcoded ReactFlow demo elements (lines ~3566–3578):** same fix as 13c.

---

## Files NOT to touch

- `docs/ai-log/archived/` — frozen history
- `infra/de3-gui-pkg/_application/de3-gui/docs/ai-log/` — frozen history
- `infra/maas-pkg/_docs/background-processes.md` — illustrative example paths;
  low-value change, leave for a dedicated docs pass
- `infra/maas-pkg/_docs/README.md` — GCS bucket name in a gsutil example;
  specific to one install, leave for a dedicated docs pass
- `scripts/ai-only-scripts/` — operational scripts; pwy refs are config-value
  references, not naming problems

---

## Verification

After all edits:
```bash
grep -r "pwy" \
  --include="*.py" --include="*.hcl" --include="*.yaml" --include="*.sh" \
  --include="*.md" --include="*.tf" \
  $(git ls-files | grep -v "infra/pwy-home-lab-pkg" | grep -v "docs/ai-log/archived" \
    | grep -v "de3-gui-pkg/.*docs/ai-log" | grep -v "scripts/ai-only-scripts") \
  | grep -v "pwy-home-lab-pkg"
```
Expected result: zero matches (or only remaining hits are in ai-only-scripts that
reference config values, which are acceptable).

---

## Open Questions

None — this is a pure rename/cleanup with no architectural decisions.
