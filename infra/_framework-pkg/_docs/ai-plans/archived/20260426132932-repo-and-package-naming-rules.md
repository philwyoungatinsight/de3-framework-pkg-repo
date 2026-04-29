# Plan: Repo and Package Naming Rules — Config Block + fw-repo-mgr Enforcement

## Objective

The `framework_package_naming_rules` block already exists in
`infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml`
but is not yet present in the de3-runner template (the default tier-3 config), and
fw-repo-mgr does not read it — validation is currently hardcoded (one check: package
names must end in `-pkg`). This plan:

1. Copies the block into the de3-runner template's `framework_repo_manager.yaml`.
2. Replaces the hardcoded `-pkg` suffix check in fw-repo-mgr with a general
   rule-driven validation function.
3. Adds a standalone `validate` subcommand to fw-repo-mgr.

## Context

**3-tier config lookup** (highest wins):
1. `$GIT_ROOT/config/framework_repo_manager.yaml`
2. `$_FRAMEWORK_CONFIG_PKG_DIR/_config/_framework_settings/framework_repo_manager.yaml`  ← pwy-home-lab-pkg's copy (has the block)
3. `$_FRAMEWORK_PKG_DIR/_config/_framework_settings/framework_repo_manager.yaml`         ← de3-runner template (missing the block)

**Canonical file paths** — `infra/_framework-pkg` in pwy-home-lab-pkg is a symlink chain:
```
infra/_framework-pkg
  → ../_ext_packages/de3-runner/main/infra/_framework-pkg
    → /home/pyoung/git/de3-ext-packages/de3-runner/main/infra/_framework-pkg
```
All de3-runner file edits go to `/home/pyoung/git/de3-ext-packages/de3-runner/main/`.
That clone must be committed and pushed to GitHub so the rules survive `pkg-mgr --sync`.

**Current hardcoded check** (fw-repo-mgr line 213):
```python
invalid_names = [p['name'] for p in pkgs if not p['name'].endswith('-pkg')]
```
This will be removed and replaced with rule-driven validation.

**Existing rules in pwy-home-lab-pkg config**:
```yaml
framework_package_naming_rules:
  - name: repo_names_must_be_unique
    value: true
  - name: repo_names_must_begin_with
    value: de3-
  - name: repo_names_must_begin_with
    value: -pkg-repo                    # ⚠️ open question — see below
  - name: repo_names_must_not_contain_special_chars
    value: true
  - name: package_names_must_be_unique
    value: true
  - name: package_names_must_be_valid_identifiers
    value: true
  - name: package_names_must_not_contain_special_chars
    value: true
```

## Open Questions

> **Q1 — Typo in second `repo_names_must_begin_with` rule?**
>
> The config has two `repo_names_must_begin_with` rules:
> - `value: de3-`     → `de3-aws-pkg`, `de3-unifi-pkg`, etc. start with this ✓
> - `value: -pkg-repo` → NO repo name starts with `-pkg-repo`; `proxmox-pkg-repo` ENDS with it
>
> This looks like a copy-paste typo — the second rule should be:
> ```yaml
> - name: repo_names_must_end_with
>   value: -pkg-repo
> ```
>
> **Proposed fix**: change `repo_names_must_begin_with` → `repo_names_must_end_with` for the
> `-pkg-repo` entry in **both** config files (pwy-home-lab-pkg and de3-runner template).
> Also add `repo_names_must_end_with` as a supported rule type in fw-repo-mgr.
>
> Answer yes/no before execution.

> **Q2 — OR logic for repeated rule names?**
>
> With multiple `repo_names_must_begin_with` (or `end_with`) entries, the intended
> semantics are: a repo name is valid if it matches **at least one** of the listed values
> (OR logic), not all of them.
> With OR logic + the typo fix from Q1:
> - `proxmox-pkg-repo` → valid (ends with `-pkg-repo`) ✓
> - `de3-aws-pkg` → valid (begins with `de3-`) ✓
> - `pwy-home-lab-pkg` (in de3-runner template) → fails both rules ✗
>
> This raises a sub-question: **should pwy-home-lab-pkg in de3-runner's config be
> excluded from validation** (it's a deployment repo, not a generated framework repo),
> or should the naming rules be relaxed to allow it?
>
> Options:
> a) Add a per-repo `skip_naming_validation: true` flag
> b) Relax `repo_names_must_begin_with` in the de3-runner template to also include `pwy-`
> c) Keep pwy-home-lab-pkg entry but remove naming rules from de3-runner template
>    (deployment repos define their own rules in tier-2 config; template has none)
>
> **Recommended**: option (c) — the de3-runner template gets the block as a commented-out
> example with default values, not as live rules. Live rules belong in deployment configs
> (tier 2), which can customize them. This avoids the template enforcing rules on itself.
>
> Answer yes/no (or choose a/b/c) before execution.

## Files to Create / Modify

### `infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml` — modify
*(canonical path: `/home/pyoung/git/de3-ext-packages/de3-runner/main/infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml`)*

Add the `framework_package_naming_rules` block after the `framework_settings_sops_template`
comment block, before `framework_repos`. Based on the recommended answer to Q2(c), add as
a **commented-out example** (not live rules) in the template:

```yaml
  # Naming rules enforced during fw-repo-mgr build/validate.
  # Deployment repos override these in their tier-2 framework_repo_manager.yaml.
  # Supported rule names:
  #   repo_names_must_be_unique            value: true
  #   repo_names_must_begin_with           value: <prefix>   (multiple = OR)
  #   repo_names_must_end_with             value: <suffix>   (multiple = OR)
  #   repo_names_must_not_contain_special_chars  value: true
  #   package_names_must_be_unique         value: true
  #   package_names_must_be_valid_identifiers    value: true   (enforces -pkg suffix)
  #   package_names_must_not_contain_special_chars value: true
  #
  #framework_package_naming_rules:
  #  - name: repo_names_must_be_unique
  #    value: true
  #  - name: repo_names_must_begin_with
  #    value: de3-
  #  - name: repo_names_must_end_with
  #    value: -pkg-repo
  #  - name: repo_names_must_not_contain_special_chars
  #    value: true
  #  - name: package_names_must_be_unique
  #    value: true
  #  - name: package_names_must_be_valid_identifiers
  #    value: true
  #  - name: package_names_must_not_contain_special_chars
  #    value: true
```

### `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml` — modify
*(this repo, tier-2 config)*

Fix the typo: change `repo_names_must_begin_with` + `value: -pkg-repo` to
`repo_names_must_end_with` + `value: -pkg-repo`.

Before:
```yaml
  framework_package_naming_rules:
    - name: repo_names_must_be_unique
      value: true
    - name: repo_names_must_begin_with
      value: de3-
    - name: repo_names_must_begin_with      # ← typo
      value: -pkg-repo
    ...
```

After:
```yaml
  framework_package_naming_rules:
    - name: repo_names_must_be_unique
      value: true
    - name: repo_names_must_begin_with
      value: de3-
    - name: repo_names_must_end_with        # ← fixed
      value: -pkg-repo
    ...
```

### `infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr` — modify
*(canonical: `/home/pyoung/git/de3-ext-packages/de3-runner/main/infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr`)*

**Change 1** — add `_validate_naming_rules()` function (insert after `_list_repos`,
before `_resolve_source`):

```bash
# ---------------------------------------------------------------------------
# Validate framework_package_naming_rules from config.
# Reads all repo names and package names from framework_repos; applies each rule.
# Multiple rules with the same name use OR logic (any match is valid).
# Exits 1 and prints errors to stderr if any rule fails; exits 0 otherwise.
# Pass a repo name to scope validation to one repo; pass "" to validate all.
# ---------------------------------------------------------------------------
_validate_naming_rules() {   # _validate_naming_rules [<repo_name>]
  local scope="${1:-}"
  [[ -z "$FW_MGR_CFG" ]] && return 0
  python3 - "$FW_MGR_CFG" "$scope" <<'PYEOF'
import sys, yaml, pathlib, re
from collections import defaultdict

cfg_path, scope = sys.argv[1], sys.argv[2]
d = yaml.safe_load(pathlib.Path(cfg_path).read_text()) or {}
fm = d.get('framework_repo_manager', {})
rules = fm.get('framework_package_naming_rules', [])
if not rules:
    sys.exit(0)

all_repos = fm.get('framework_repos', [])
repos = [r for r in all_repos if not scope or r.get('name') == scope]
repo_names = [r.get('name', '') for r in repos]

all_pkg_names = []
template = fm.get('framework_package_template')
if template:
    all_pkg_names.append(template.get('name', ''))
for r in repos:
    for p in r.get('framework_packages', []):
        all_pkg_names.append(p.get('name', ''))

# Group repeated rule names — OR logic within each group
rule_groups = defaultdict(list)
for rule in rules:
    rule_groups[rule['name']].append(rule['value'])

errors = []
for rule_name, values in rule_groups.items():
    if rule_name == 'repo_names_must_be_unique':
        seen = {}
        for n in repo_names:
            seen[n] = seen.get(n, 0) + 1
        dupes = [n for n, c in seen.items() if c > 1]
        if dupes:
            errors.append(f"repo_names_must_be_unique: duplicate repo names: {dupes}")

    elif rule_name == 'repo_names_must_begin_with':
        for n in repo_names:
            if not any(n.startswith(str(v)) for v in values):
                errors.append(f"repo_names_must_begin_with: '{n}' must begin with one of {values}")

    elif rule_name == 'repo_names_must_end_with':
        for n in repo_names:
            if not any(n.endswith(str(v)) for v in values):
                errors.append(f"repo_names_must_end_with: '{n}' must end with one of {values}")

    elif rule_name == 'repo_names_must_not_contain_special_chars':
        for n in repo_names:
            if not re.match(r'^[a-z0-9][a-z0-9-]*$', n):
                errors.append(f"repo_names_must_not_contain_special_chars: '{n}' (only a-z, 0-9, - allowed)")

    elif rule_name == 'package_names_must_be_unique':
        seen = {}
        for n in all_pkg_names:
            seen[n] = seen.get(n, 0) + 1
        dupes = [n for n, c in seen.items() if c > 1]
        if dupes:
            errors.append(f"package_names_must_be_unique: duplicate package names: {dupes}")

    elif rule_name == 'package_names_must_be_valid_identifiers':
        for n in all_pkg_names:
            if not n.endswith('-pkg'):
                errors.append(f"package_names_must_be_valid_identifiers: '{n}' must end in '-pkg'")

    elif rule_name == 'package_names_must_not_contain_special_chars':
        for n in all_pkg_names:
            if not re.match(r'^[a-z0-9][a-z0-9-]*$', n):
                errors.append(f"package_names_must_not_contain_special_chars: '{n}' (only a-z, 0-9, - allowed)")

    else:
        errors.append(f"Unknown rule name: '{rule_name}'")

if errors:
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}
```

**Change 2** — remove hardcoded check in `_write_framework_packages_yaml` (lines 213–217);
replace with a call to `_validate_naming_rules` scoped to the repo being built.

Before (inside `_write_framework_packages_yaml` Python block):
```python
invalid_names = [p['name'] for p in pkgs if not p['name'].endswith('-pkg')]
if invalid_names:
    for n in invalid_names:
        print(f"ERROR: package name '{n}' must end in '-pkg'", file=sys.stderr)
    sys.exit(1)
```

After — remove those 5 lines entirely (validation handled by `_validate_naming_rules`).

**Change 3** — call `_validate_naming_rules` at the start of `_build_repo()`, after
`repo_base` is resolved (before Step 1):

```bash
  # Validate naming rules from config before building
  _validate_naming_rules "$repo_name"
```

**Change 4** — add `validate` subcommand to `usage()`:

```
  fw-repo-mgr validate [<name>]              Validate naming rules (all or named repo)
```

**Change 5** — add `validate` to the CLI dispatch `while case` loop and `case "${CMD:-help}"`:

```bash
    -v|validate)   CMD="validate"; shift ;;
```

```bash
  validate)
    _validate_naming_rules "${REPO_NAME:-}"
    echo "Naming rules OK."
    ;;
```

## Execution Order

1. Fix typo in `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml`
   (`repo_names_must_begin_with` → `repo_names_must_end_with` for the `-pkg-repo` entry).
2. Add the commented-out `framework_package_naming_rules` block to de3-runner's
   `framework_repo_manager.yaml`.
3. Edit `fw-repo-mgr`:
   a. Add `_validate_naming_rules()` function (after `_list_repos`, before `_resolve_source`)
   b. Remove the hardcoded check from `_write_framework_packages_yaml`
   c. Call `_validate_naming_rules "$repo_name"` at the start of `_build_repo`
   d. Add `-v|validate` to usage + CLI dispatch
4. Commit de3-runner changes in `/home/pyoung/git/de3-ext-packages/de3-runner/main/`.
5. Commit pwy-home-lab-pkg changes in this repo (the config fix + version bump).

## Verification

```bash
# Test validate subcommand — should exit 0 with "Naming rules OK."
cd /home/pyoung/git/pwy-home-lab-pkg
source set_env.sh
fw-repo-mgr validate

# Test per-repo validation
fw-repo-mgr validate de3-unifi-pkg

# Confirm hardcoded check is gone and rule-based check fires instead
# (add a dummy bad package name to a test config and confirm the right error fires)
```
