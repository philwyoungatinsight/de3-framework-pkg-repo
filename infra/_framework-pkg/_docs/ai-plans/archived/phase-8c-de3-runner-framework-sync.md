# Phase 8C — de3-runner framework sync

## The Problem

After Phases 8A and 8B, de3-runner's tg-scripts now call:

```bash
{{ lookup('env', '_FRAMEWORK_DIR') }}/_config-mgr/run set <path> <key> <value> --sops
```

But de3-runner's own `infra/default-pkg/_framework/` does **not** contain `_config-mgr/`.
When de3-runner is run standalone (its own `set_env.sh` → its own `root.hcl`), these
scripts will fail immediately with "No such file or directory".

Additionally de3-runner's `root.hcl` still uses `sops_decrypt_file()` and reads from
`infra/<pkg>/_config/` directly — not from `$_CONFIG_DIR`. Running terragrunt against
de3-runner standalone would also fail because `get_env("_CONFIG_DIR")` would be unset.

**Summary of divergence between de3-runner and pwy-home-lab-pkg frameworks:**

| File | de3-runner | pwy-home-lab-pkg |
|------|-----------|-----------------|
| `set_env.sh` | no `$_CONFIG_DIR`, no `config-mgr generate` | exports `$_CONFIG_DIR`, calls generate |
| `root.hcl` | `sops_decrypt_file()`, reads `infra/<pkg>/_config/` | plain `file()`, reads `$_CONFIG_DIR` |
| `_framework/` | no `_config-mgr/` | has `_config-mgr/` |
| `validate-config.py` | no RULE 6 | RULE 6 (config_source chain check) |
| `generate_ansible_inventory.py` | reads `infra/*/_config/` glob | reads `$_CONFIG_DIR` |
| `config_base` role | `community.sops.load_vars` | plain `include_vars`, no SOPS |
| `unit-mgr` | no config_source resolution | resolves config_source |

## The Core Question

**What is the intended lifecycle for repos that import de3-runner?**

**Case 1: Every deployment repo has its own `infra/default-pkg/`** (like pwy-home-lab-pkg)

de3-runner's `infra/default-pkg/` is only used when de3-runner is run standalone
(e.g. by the de3-runner maintainer). Importing repos use their own framework and are
unaffected by de3-runner's framework state.

*Implication*: Phase 8C just means keeping de3-runner's standalone mode working. We port
the full config-mgr + framework changes into de3-runner's own `infra/default-pkg/`.

**Case 2: Some repos import de3-runner and inherit its `infra/default-pkg/` as their framework**

Those repos would be broken right now (Phase 8A scripts call config-mgr which doesn't
exist). Phase 8C is urgent and needs to happen before those repos sync to the new de3-runner.

*Implication*: Same fix — port config-mgr into de3-runner — but urgency is higher.

**Case 3: The framework is meant to live ONLY in deployment repos (not in de3-runner)**

de3-runner's `infra/default-pkg/` should be removed or left minimal. Package scripts
would need a fallback when config-mgr is absent, OR de3-runner would simply require
importers to provide a compatible framework.

*Implication*: Either (a) add a graceful fallback in the Phase 8A scripts, or (b) remove
de3-runner's framework entirely and document that a framework-providing repo is required.

## Open Questions for User

1. **What model do importing repos follow?** Do they all bring their own `infra/default-pkg/`,
   or are some expected to rely on de3-runner's?

2. **Is de3-runner currently used standalone?** If not, we can deprioritize the standalone
   path and focus only on making importers work.

3. **Who maintains de3-runner's framework?** If pwy-home-lab-pkg is the primary development
   environment and de3-runner's framework always lags, should we consider making
   de3-runner's `infra/default-pkg/` a symlink or submodule reference to avoid drift?

4. **Fallback vs full port?** Should the Phase 8A tg-scripts fall back to raw `sops --set`
   when config-mgr is unavailable, or should config-mgr be a hard requirement for de3-runner?

## Proposed Approach (pending user input)

**Option A — Full port (recommended if Case 1 or 2)**

Copy `_config-mgr/` and all framework changes into de3-runner's `infra/default-pkg/`.
This is a mechanical port: same files, same code. de3-runner becomes self-contained and
works both standalone and when imported.

Downside: two copies of the framework to maintain. Drift will recur unless there's a
process to keep them in sync.

**Option B — Graceful fallback in tg-scripts**

In the Phase 8A tg-scripts, check for `$_FRAMEWORK_DIR/_config-mgr/run`:

```yaml
ansible.builtin.command: >-
  {% if lookup('env', '_FRAMEWORK_DIR') + '/_config-mgr/run' is file %}
  {{ lookup('env', '_FRAMEWORK_DIR') }}/_config-mgr/run set <path> <key> <value> --sops
  {% else %}
  sops --set '["<pkg>_secrets"]["config_params"]["<path>"]["<key>"] "<value>"' <file>
  {% endif %}
```

Keeps de3-runner working with either framework. More complex tg-scripts.

**Option C — de3-runner declares config-mgr as a framework requirement**

Remove de3-runner's `infra/default-pkg/` (or leave a stub that fails clearly).
Document: "de3-runner requires a framework-providing repo (e.g. pwy-home-lab-pkg)."
No standalone mode.

Simplest long-term, but breaking change for anyone using de3-runner standalone today.
