# Plan: Review and Fix unit-mgr / pkg-mgr

## Objective

Fix three real bugs found during code review of `framework/unit-mgr` and `framework/pkg-mgr`,
remove dead code, and make READMEs accurate. No architectural changes — all fixes are small
and targeted.

---

## Context

Several fixes were already made in earlier sessions (see recent ai-log entries). What remains:

### Bug 1 — `sops_secrets.py` same-package move: two SOPS writes with a vulnerability window

`migrate_secrets()` for a same-package **move** performs two separate `_sops_encrypt_from_dict`
calls on the same file:

1. **Write 1** (line 81): re-encrypts source WITH old keys deleted
2. **Write 2** (lines 97–103): re-reads source, adds renamed keys, re-encrypts again

Between write 1 and write 2, if the process is killed, the secrets file has the old keys
**deleted** and the renamed keys **not yet added**. Those secrets are permanently gone with
no recovery path.

For cross-package move this is fine (different files written). For same-package copy this is
also fine (source is never written in write 1). Only same-package **move** is affected.

Fix: skip write 1 for same-package move; add renamed keys to `src_data` in-memory (before any
write), then do a single write. `config_params` is already in scope with old keys removed.

### Bug 2 — `config_yaml.py` `_rename_keys_inplace`: dead `new_keys[k]` branch

`_rename_keys_inplace(cfg, old_keys, new_keys)` is called with:
- `old_keys` = `keys_to_migrate` → keyed by OLD key strings
- `new_keys` = `renamed` → keyed by NEW key strings

At line 162, the check `if k in new_keys` always evaluates **False** because `k` is an old
key and `new_keys` uses new keys. The `next()` fallback always executes. The pyyaml path
(lines 174–176) has the same pattern.

This works by accident (Python dict insertion order is stable), but is confusing and wrong as
written. Fix: change the signature to accept a direct `old_to_new` mapping `{old_key: new_key}`
and update the two call sites.

### Bug 3 — `pkg-mgr/run` rename warning calls `_gcs_bucket` three times

The warning block added for `rename --skip-state` calls `$(_gcs_bucket)` three times in
echo statements (lines in the Phase 6 skip block). Each call invokes a Python subprocess.
Fix: capture once into a local variable before the echo statements.

### Dead code — `main.py` `external_outbound` category never produced

`scan_dependencies()` in `dependency_scanner.py` only finds references that **point into**
the src tree. A reference FROM src pointing OUTSIDE src is skipped by the `if not
is_pointing_into_src: continue` guard. The `"external_outbound"` category is never produced.

In `main.py`, `external_outbound` is therefore always an empty list, and the log line
`"External outbound refs (no action): 0"` is always zero. The unit-mgr README Phase 2 table
also documents this non-existent category.

Fix: remove the dead filter and log line from `main.py`; update the Phase 2 table in the
README to remove the external_outbound row.

### README inaccuracies

- **`unit-mgr/README.md`** Phase 2 table: lists "External outbound" category that the scanner
  never produces.
- **`pkg-mgr/README.md`** rename phases: the numbered list has 8 items but the code has 7
  distinct sections — README items 2 and 3 ("config file rename" and "rename YAML key") are
  both performed in code Phase 2 as one git mv + `_rename_pkg_yaml_keys` call.

---

## Open Questions

None — ready to proceed.

---

## Files to Create / Modify

### `framework/unit-mgr/unit_mgr/sops_secrets.py` — modify

Change `migrate_secrets` so same-package move uses a single write.

Replace lines 79–103 with:

```python
    # Re-encrypt source for cross-package move (remove old keys from src file).
    # Same-package move is handled below in a single write to avoid a vulnerability
    # window where old keys are deleted but renamed keys not yet written.
    if operation == "move" and src_pkg != dst_pkg:
        _sops_encrypt_from_dict(src_sops_path, src_data)

    # Merge into destination
    if src_pkg == dst_pkg:
        if operation == "copy":
            # Source unchanged; re-read and add renamed keys alongside originals.
            dst_data = _sops_decrypt(src_sops_path)
            dst_top = dst_data.get(f"{dst_pkg}_secrets", {}) or {}
            dst_cfg = dst_top.get("config_params", {}) or {}
            dst_cfg.update(moved)
            dst_top["config_params"] = dst_cfg
            dst_data[f"{dst_pkg}_secrets"] = dst_top
            _sops_encrypt_from_dict(src_sops_path, dst_data)
        else:
            # Same-package move: old keys already removed from src_data in-memory above.
            # Add renamed keys and write once (single SOPS operation — no vulnerability window).
            config_params.update(moved)
            src_top["config_params"] = config_params
            src_data[f"{src_pkg}_secrets"] = src_top
            _sops_encrypt_from_dict(src_sops_path, src_data)
    else:
        # Cross-package: src already written above; write dst now.
        if dst_sops_path.exists():
            dst_data = _sops_decrypt(dst_sops_path)
        else:
            dst_data = {f"{dst_pkg}_secrets": {"config_params": {}}}

        dst_top = dst_data.get(f"{dst_pkg}_secrets", {}) or {}
        dst_cfg = dst_top.get("config_params", {}) or {}
        dst_cfg.update(moved)
        dst_top["config_params"] = dst_cfg
        dst_data[f"{dst_pkg}_secrets"] = dst_top
        _sops_encrypt_from_dict(dst_sops_path, dst_data)
```

### `framework/unit-mgr/unit_mgr/config_yaml.py` — modify

**Change 1** — In `migrate_config_params`, build an explicit `old_to_new` dict and pass it
instead of `renamed`:

```python
    if not is_cross_package:
        # Same package — rename keys in place
        cfg = src_top.get("config_params", {})
        if cfg is None:
            cfg = {}
        if operation == "move":
            old_to_new = {k: dst_rel + k[len(src_rel):] for k in keys_to_migrate}
            new_cfg = _rename_keys_inplace(cfg, old_to_new)
            src_top["config_params"] = new_cfg
            src_data[src_pkg] = src_top
            _save_yaml(src_yaml_path, src_data, src_yml)
        else:
            # copy: add new keys but keep old ones too
            for old_k in keys_to_migrate:
                new_k = dst_rel + old_k[len(src_rel):]
                cfg[new_k] = cfg[old_k]
            src_top["config_params"] = cfg
            src_data[src_pkg] = src_top
            _save_yaml(src_yaml_path, src_data, src_yml)
```

(The cross-package block is unchanged — it uses `renamed` directly, no `_rename_keys_inplace`.)

**Change 2** — Rewrite `_rename_keys_inplace` to take `old_to_new: dict[str, str]`:

```python
def _rename_keys_inplace(cfg: Any, old_to_new: dict) -> Any:
    """Return a new ordered mapping with keys in old_to_new renamed.

    Keys not in old_to_new are passed through unchanged.
    Preserves insertion order.
    """
    if _HAS_RUAMEL:
        from ruamel.yaml.comments import CommentedMap
        result = CommentedMap()
        for k, v in cfg.items():
            result[old_to_new.get(k, k)] = v
        return result
    else:
        return {old_to_new.get(k, k): v for k, v in cfg.items()}
```

### `framework/unit-mgr/unit_mgr/main.py` — modify

Remove the dead `external_outbound` filter and its log line. Change the Phase 2 logging block
(currently lines ~219–233) from:

```python
    external_inbound = [r for r in dep_refs if r.category == "external_inbound"]
    external_outbound = [r for r in dep_refs if r.category == "external_outbound"]

    log(f"  Internal dependency refs (auto-updated): {sum(1 for r in dep_refs if r.category == 'internal')}")
    log(f"  External outbound refs (no action):      {len(external_outbound)}")
    log(f"  External inbound refs (manual update):   {len(external_inbound)}")
```

to:

```python
    external_inbound = [r for r in dep_refs if r.category == "external_inbound"]

    log(f"  Internal refs (auto-updated):   {sum(1 for r in dep_refs if r.category == 'internal')}")
    log(f"  External inbound refs (manual): {len(external_inbound)}")
```

### `framework/pkg-mgr/run` — modify

In the Phase 6 skip block of `_cmd_rename`, cache `_gcs_bucket` once. Find the block:

```bash
    if [[ "$dry_run" == false ]] && _gcs_state_exists_for_pkg "$src"; then
      echo "WARNING: --skip-state was passed but GCS state exists under $src/." >&2
      echo "         The package is now renamed to '$dst' but state remains at gs://$(_gcs_bucket)/$src/" >&2
      echo "         It will be ORPHANED (unreachable). Migrate manually:" >&2
      echo "           gsutil -m cp -r gs://$(_gcs_bucket)/$src/ gs://$(_gcs_bucket)/$dst/" >&2
      echo "           gsutil -m rm -r gs://$(_gcs_bucket)/$src/" >&2
    else
```

Replace with:

```bash
    if [[ "$dry_run" == false ]] && _gcs_state_exists_for_pkg "$src"; then
      local warn_bucket; warn_bucket=$(_gcs_bucket)
      echo "WARNING: --skip-state was passed but GCS state exists under $src/." >&2
      echo "         The package is now renamed to '$dst' but state remains at gs://$warn_bucket/$src/" >&2
      echo "         It will be ORPHANED (unreachable). Migrate manually:" >&2
      echo "           gsutil -m cp -r gs://$warn_bucket/$src/ gs://$warn_bucket/$dst/" >&2
      echo "           gsutil -m rm -r gs://$warn_bucket/$src/" >&2
    else
```

### `framework/unit-mgr/README.md` — modify

**Change 1** — Phase 2 table: remove the "External outbound" row and update the description.

Replace the three-row category table:

```
| Category | Description | Action |
|----------|-------------|--------|
| **Internal** | Reference is from a file inside `src` tree, to a unit also inside `src` tree | Will be auto-updated in Phase 4b |
| **External inbound** | Reference is from a file **outside** `src` tree, to a unit **inside** `src` tree | **Report as warning** — the referencing file won't be auto-patched |
| **External outbound** | Reference is from a file inside `src` tree, to a unit **outside** `src` tree | Note in log; no action needed |
```

with:

```
| Category | Description | Action |
|----------|-------------|--------|
| **Internal** | Reference is from a file inside `src` tree, to a unit also inside `src` tree | Will be auto-updated in Phase 4b |
| **External inbound** | Reference is from a file **outside** `src` tree, to a unit **inside** `src` tree | **Report as warning** — the referencing file won't be auto-patched |
```

**Change 2** — Update the Phase 2 log description to remove "External outbound refs":

Replace:
```
log(f"  External outbound refs (no action):      {len(external_outbound)}")
```
…reference in any prose/description with just the two remaining categories.

### `framework/pkg-mgr/README.md` — modify

Fix the rename phase list. Currently 8 items where items 2 and 3 are actually a single
atomic code phase (one `git mv` + one Python key-rename). Collapse to 7:

Replace:
```
1. `git mv infra/<src> infra/<dst>` — filesystem rename
2. `git mv infra/<dst>/_config/<src>.yaml infra/<dst>/_config/<dst>.yaml` — config file rename
3. Rename top-level YAML key (`<src>:` → `<dst>:`) and all `config_params` sub-keys
   (`<src>/…` → `<dst>/…`) inside the config file (uses `ruamel.yaml` to preserve comments)
4. Decrypt SOPS secrets...
5. String-substitute...
6. Scan all .hcl files...
7. Migrate GCS state...
8. Update `name:` field...
```

with:
```
1. `git mv infra/<src> infra/<dst>` — filesystem rename
2. `git mv infra/<dst>/_config/<src>.yaml infra/<dst>/_config/<dst>.yaml` then rename the
   top-level YAML key (`<src>:` → `<dst>:`) and all `config_params` sub-keys in-place
   (uses `ruamel.yaml` to preserve comments)
3. Decrypt SOPS secrets, rename `<src>_secrets:` key and `config_params` sub-keys, `git mv`
   the file, re-encrypt with `sops --encrypt --output` — **single write, no vulnerability window**
4. String-substitute `infra/<src>/` → `infra/<dst>/` in all `.hcl` files under the new dir
5. Scan all `.hcl` files across the repo; warn about external references that need manual update
6. Migrate GCS Terraform state files (`gsutil cp` + `gsutil rm` per file) — skipped with
   `--skip-state`
7. Update `name:` field in `framework_packages.yaml`
```

---

## Execution Order

1. `sops_secrets.py` — fix double-write (most critical)
2. `config_yaml.py` — fix `_rename_keys_inplace` (depends on understanding current call sites)
3. `main.py` — remove dead `external_outbound` code
4. `pkg-mgr/run` — fix triple `_gcs_bucket` call
5. `unit-mgr/README.md` — remove external_outbound from Phase 2 table
6. `pkg-mgr/README.md` — fix phase count in rename section

---

## Verification

```bash
# 1. Syntax check Python files
python3 -m py_compile framework/unit-mgr/unit_mgr/sops_secrets.py && echo "sops OK"
python3 -m py_compile framework/unit-mgr/unit_mgr/config_yaml.py   && echo "config_yaml OK"
python3 -m py_compile framework/unit-mgr/unit_mgr/main.py           && echo "main OK"

# 2. No remaining dead code
grep -n "external_outbound" framework/unit-mgr/unit_mgr/main.py
# expected: no output

# 3. Single _gcs_bucket call in the warning block
grep -c '_gcs_bucket' framework/pkg-mgr/run
# count should decrease by 2 vs current

# 4. new_keys[k] dead branch gone
grep -n "new_keys\[k\]" framework/unit-mgr/unit_mgr/config_yaml.py
# expected: no output

# 5. README phase count
grep -c "^\d\." framework/pkg-mgr/README.md  # rough check — 7 phases in rename list
```
