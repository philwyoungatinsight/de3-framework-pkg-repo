# Plan: Simplify Skip Parameters

## Objective

Remove the dead `_skip_on_build_without_inheritance` unit-level skip parameter and its
corresponding `_skip_on_build_exact` local in `root.hcl`. This leaves exactly two skip
features as the user intends: one wave-level skip (`_skip_on_wave_run`) and one
unit-level skip (`_skip_on_build`). Also scrub the misleading "Terragrunt only allows
one exclude block" complaint from docs and comments — it was never a real constraint
since `root.hcl` already ORs multiple conditions into one `exclude` block.

## Context

### What exists today

Three skip parameters are documented and implemented:

1. **`_skip_on_wave_run`** (wave-level, `waves:` block) — skips during both build and
   clean; handled by the Python `run` orchestrator.
2. **`_skip_on_build`** (unit-level, `config_params:`, inherited) — excludes unit subtrees
   from all Terraform actions; read from `local.unit_params._skip_on_build` in root.hcl.
3. **`_skip_on_build_without_inheritance`** (unit-level, `config_params:`, NOT inherited)
   — reads from `local._config_params[local.rel_path]._skip_on_build_without_inheritance`;
   stored in `_skip_on_build_exact` local; ORd into the same exclude block.

### What needs removing

`_skip_on_build_without_inheritance` / `_skip_on_build_exact`:
- Zero usages in any `config_params` YAML across the entire repo.
- Only referenced in `root.hcl` (implementation + comment) and docs.
- Dead code — can be deleted outright.

### The misleading "one exclude block" complaint

Several files contain text claiming that the Terragrunt "one exclude block" limitation
prevents having unit-level clean-skip. This is a misframing: `root.hcl` already
combines `_wave_skip || _skip_on_build || _skip_on_build_exact` in ONE block. The
limitation is that actions must be a static list (cannot be "apply only" vs
"destroy only" per-condition), not that you cannot have multiple conditions. These
comments should be removed or corrected.

### Files to change

| File | What changes |
|------|-------------|
| `root.hcl` | Remove `_skip_on_build_exact` local and its `_skip_on_build_without_inheritance` read; update comment block; simplify exclude block |
| `docs/framework/skip-parameters.md` | Remove `_skip_on_build_without_inheritance` row from tables and text; remove misleading "one exclude block" complaint; update summary table |
| `docs/framework/unit_params.md` | Remove `_skip_on_build_without_inheritance` section; update note below `_skip_on_build_without_inheritance` removal |
| `CLAUDE.md` | Remove `_skip_on_build_without_inheritance` from `_skip_FOO` params line; remove "one exclude block" complaint |

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `root.hcl` — modify

**a) Comment block (lines 314–340):** Replace the entire unit skip flags comment and
the two locals with a simplified version:

```hcl
  # ── Unit skip flags ───────────────────────────────────────────────────────────
  #
  # _skip_on_build (INHERITED via unit_params):
  #   Set at an ancestor config_params path to disable deployment of an entire
  #   subtree (e.g. "examples/" trees shipped with a package but not run by
  #   default). All descendants inherit the flag via ancestor-path merging.
  #   Override with _skip_on_build: false at a child path to re-enable a subtree.
  #   Excluded from ALL terraform actions (actions = ["all"] in the exclude block
  #   below). Since these units are never deployed there is no state to destroy.
  #
  # _skip_on_wave_run — wave-level, handled by the Python orchestrator in run:
  #   Set _skip_on_wave_run: true on a wave definition in <pkg>.yaml. The `run`
  #   script skips the wave during both build and clean passes. No HCL change
  #   needed — this flag is read and applied entirely in Python.
  #
  # _FORCE_DELETE=YES overrides all skip flags so make clean-all destroys every
  # unit unconditionally, including _skip_on_build example trees.
  #
  _force_delete  = get_env("_FORCE_DELETE", "") == "YES"
  _skip_on_build = try(tobool(local.unit_params._skip_on_build), false)
```

**b) Exclude block comment (lines 383–396):** Replace with:

```hcl
# ── Wave / unit skip ──────────────────────────────────────────────────────────
# Two conditions trigger the exclude (OR'd):
#   _wave_skip       — unit's wave doesn't match TG_WAVE filter
#   _skip_on_build   — ancestor-inherited subtree skip flag (config_params)
# Both map to actions = ["all"]: no apply, plan, init, output, or destroy.
# Wave-level _skip_on_wave_run is handled by the Python orchestrator in run,
# not here. _FORCE_DELETE=YES (set by make clean-all) disables this block
# entirely so every unit is destroyed unconditionally.
exclude {
  if      = !local._force_delete && (local._wave_skip || local._skip_on_build)
  actions = ["all"]
}
```

### `docs/framework/skip-parameters.md` — modify

**a)** Remove the "Non-inherited parameters" subsection (the entire block from
`### Non-inherited parameters` through the table row for `_skip_on_build_without_inheritance`).

**b)** Remove the "Unit-level `_skip_on_wave_run` is not supported" paragraph (was
the misleading one-exclude-block complaint — it now lives immediately after the
non-inherited table removal):

```
### Unit-level `_skip_on_wave_run` is not supported
...
To skip a unit during both build and clean, place it in its own wave and set `_skip_on_wave_run: true` on that wave definition.
```

**c)** In the `make clean-all` section, replace the sentence referencing
`_skip_on_build`:

Before:
```
- `root.hcl` reads `_FORCE_DELETE` and disables the `exclude` block entirely, so `_skip_on_build` units are destroyed like any other unit.
```
(no change needed here — this sentence is still accurate)

**d)** Update the summary table — remove the `_skip_on_build_without_inheritance` row:

```markdown
| Parameter | Scope | Inherits | Skips on build | Skips on clean | Ignored by clean-all |
|-----------|-------|----------|----------------|----------------|----------------------|
| Wave `_skip_on_wave_run` | Wave | N/A | Yes | Yes | Yes |
| `_skip_on_build` | Unit (config_params) | Yes | Yes | No | Yes |
```

### `docs/framework/unit_params.md` — modify

**a)** Remove the entire `### _skip_on_build_without_inheritance` section (lines 133–143
in current file), including the trailing `---` separator.

**b)** Update the note at the bottom of the `### _skip_on_build_without_inheritance`
section (which after removal will be the note at the bottom of `### _skip_on_build`):

The existing `_skip_on_build` section ends at line ~129 and the
`_skip_on_build_without_inheritance` section follows. After removing it, the note
currently in that section about `_skip_on_wave_run` not being supported should be
updated or removed. The correct replacement note (to append at the end of the
`_skip_on_build` section, before `See [skip-parameters.md]`):

```markdown
See [skip-parameters.md](skip-parameters.md) for the full reference.
```

(The existing "See skip-parameters.md" link is already at line 143 — just ensure it
remains after the section removal, associated with `_skip_on_build`.)

### `CLAUDE.md` — modify

Line 315 — replace the `_skip_FOO` params bullet:

Before:
```
- **`_skip_FOO` params**: use `_skip_on_build: true` (inherited) to disable example subtrees; use `_skip_on_build_without_inheritance` for a single unit. To skip a wave during both build and clean, use `_skip_on_wave_run: true` on the **wave definition** (unit-level `_skip_on_wave_run` is not supported — Terragrunt allows only one exclude block). **`make clean-all` ignores ALL skip flags** — no exceptions. See `docs/framework/skip-parameters.md`.
```

After:
```
- **`_skip_FOO` params**: use `_skip_on_build: true` (inherited) to disable example subtrees (set at ancestor path; children inherit). To skip a wave during both build and clean, use `_skip_on_wave_run: true` on the **wave definition**. **`make clean-all` ignores ALL skip flags** — no exceptions. See `docs/framework/skip-parameters.md`.
```

## Execution Order

1. `root.hcl` — remove `_skip_on_build_exact` local; simplify comment + exclude block
2. `docs/framework/skip-parameters.md` — remove non-inherited section + row; update summary table
3. `docs/framework/unit_params.md` — remove `_skip_on_build_without_inheritance` section
4. `CLAUDE.md` — update `_skip_FOO` params bullet

## Verification

```bash
# No references to removed parameter anywhere in active code or docs
grep -r "_skip_on_build_without_inheritance\|_skip_on_build_exact" \
  root.hcl docs/ CLAUDE.md \
  --include="*.hcl" --include="*.md" | grep -v "ai-log/archived\|claude-md-history"

# Two and only two skip features documented
grep -r "_skip_on_build\|_skip_on_wave_run" docs/framework/skip-parameters.md

# Exclude block still correct in root.hcl
grep -A3 "^exclude {" root.hcl
```
