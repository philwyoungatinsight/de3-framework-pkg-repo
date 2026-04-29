# Fix ansible inventory path — read from framework.yaml, not hardcoded

## What changed

`_read_inventory_file()` now resolves the inventory file path from
`framework.ansible_inventory.output_file` in `config/framework.yaml` (already loaded
into `_STACK_CONFIG["lab_stack"]["ansible_inventory"]`) rather than requiring it to be
hardcoded in `de3-gui-pkg.yaml`.

Relative paths from `output_file` are anchored to `$_DYNAMIC_DIR` (same logic as
`generate_ansible_inventory.py`), falling back to `_STACK_DIR` when `$_DYNAMIC_DIR`
is unset.  An explicit `ansible_inventory_path` in `de3-gui-pkg.yaml` still works as
an override (now commented out).

## Files modified

- `infra/de3-gui-pkg/_applications/de3-gui/homelab_gui/homelab_gui.py` — `_read_inventory_file()`
- `infra/de3-gui-pkg/_config/de3-gui-pkg.yaml` — removed hardcoded path; added comment explaining override slot

## Symptoms fixed

1. **`{ansible_host}` not interpolated in browser URL** — `_get_browser_url_for_node()`
   reads the inventory to resolve `{ansible_host}` tokens. With the wrong path the
   inventory was empty, so `http://{ansible_host}:5240/MAAS/r/machines` was returned
   as-is instead of `http://10.0.10.11:5240/MAAS/r/machines`.

2. **Ansible Inventory view showed nothing** — same root cause; `_read_inventory_file`
   returned `('', '')` because the path did not exist on disk.

## Why

The path had been hardcoded as `ansible/terragrunt_lab_stack/hosts.yml` (resolved
relative to `_STACK_DIR`) but the generator writes to
`$_DYNAMIC_DIR/ansible/terragrunt_lab_stack/hosts.yml`.  The canonical location is
already declared in `framework.yaml` under `framework.ansible_inventory.output_file`;
reading it from there means the GUI stays correct automatically if the path ever changes.
