# manage-unit: Unit Rename/Move/Copy Tool + GUI Refactor Panel

## Summary

Implemented the `framework/manage-unit` tool and the GUI Refactor panel as designed in `framework/manage-unit/README.md`.

## What was built

### Backend CLI: `framework/manage-unit/`

New Python CLI tool (`./framework/manage-unit/run`) that handles all four things that must stay in sync when a Terragrunt unit path changes:

1. **Filesystem directory** — `shutil.copytree` + `.terragrunt-cache` stripping
2. **Public config_params YAML** — `ruamel.yaml` round-trip rename/migrate
3. **SOPS secrets** — `sops --decrypt` / `sops --encrypt --output` (atomic, never uses `>`)
4. **GCS Terraform state** — `gsutil cp` + `gsutil rm` (verifies dst before deleting src)

Also scans all `.hcl` files for `dependencies { paths = [...] }` references into the moved tree and reports external inbound references (requiring manual update) as warnings.

Files created:
- `framework/manage-unit/run` — bash entry point (same pattern as `generate-ansible-inventory/run`)
- `framework/manage-unit/requirements.txt` — `pyyaml`, `ruamel.yaml`, `google-cloud-storage`
- `framework/manage-unit/manage_unit/__init__.py`
- `framework/manage-unit/manage_unit/main.py` — CLI phases 0–5 orchestrator
- `framework/manage-unit/manage_unit/unit_tree.py` — unit discovery (skips `.terragrunt-cache`)
- `framework/manage-unit/manage_unit/dependency_scanner.py` — HCL dep ref scanner + patcher
- `framework/manage-unit/manage_unit/config_yaml.py` — YAML config_params migration (ruamel.yaml, `ignore_aliases`, `width=4096`)
- `framework/manage-unit/manage_unit/sops_secrets.py` — SOPS secrets migration
- `framework/manage-unit/manage_unit/gcs_state.py` — GCS state blob migration
- `framework/manage-unit/manage_unit/report.py` — human log + JSON report (after `---JSON---` sentinel)

### GUI: Refactor Panel

Replaced the old clipboard copy/paste mechanism with the new Refactor panel that calls `manage-unit`.

**Removed:**
- State vars: `clipboard_unit_path`, `clipboard_unit_content`, `clipboard_config_block`, `clipboard_config_provider`, `paste_dialog_open`, `paste_pending_target`, `paste_pending_name`, `recursive_clipboard_root`, `recursive_clipboard_items`, `recursive_paste_dialog_open`, `recursive_paste_pending_target`, `recursive_paste_pending_prefix`
- Computed var: `clipboard_unit_name`
- Event handlers: `copy_unit`, `copy_recursive`, `begin_paste`, `set_paste_name`, `paste_name_keydown`, `cancel_paste`, `confirm_paste`, `begin_recursive_paste`, `set_recursive_paste_prefix`, `recursive_paste_prefix_keydown`, `cancel_recursive_paste`, `confirm_recursive_paste`
- Context menu groups: `copy_unit`, `copy_recursive`, `paste_unit`, `paste_recursive`, `clipboard` group
- Dialog overlays: paste dialog, recursive paste dialog

**Added:**
- State vars: `refactor_operation`, `refactor_src_path`, `refactor_dst_path`, `refactor_preview_result`, `refactor_running`, `refactor_result`, `refactor_error`
- Event handlers: `begin_refactor`, `set_refactor_operation`, `set_refactor_dst_path`, `clear_refactor_result`, `run_refactor_preview` (background), `run_refactor_execute` (background)
- Module helpers: `_find_manage_unit_run()`, `_parse_manage_unit_json()`
- Component: `_refactor_panel()` — Operation selector, Source (read-only), Destination input, Preview/Execute/Clear buttons, error/result display
- Context menu entry: `Refactor (move / copy)…` in the "edit" group on all nodes
- Dropdown mode: added "Refactor" as third option alongside "Unit Params" and "Waves"

## Testing

- Ran `--dry-run --json-report --skip-state` against real units: output correct
- Ran real `copy` operation with config_params migration: 2 keys migrated correctly
- Verified `.terragrunt-cache` dirs are excluded from unit discovery
- Verified `ruamel.yaml` settings (`ignore_aliases`, `width=4096`) prevent anchor injection and minimize reformatting
- GUI syntax checked: `ast.parse` OK

## Known behavior

- `ruamel.yaml` unifies multi-line folded YAML strings into single long lines on round-trip. This is cosmetic — YAML semantics are preserved. Only affects files whose `_unit_purpose` or similar long strings were manually line-wrapped.
