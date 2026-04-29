# Plan: Sync GUI Defaults from Current State

## Objective

When `state/current.yaml` is absent (first boot, wiped container, fresh clone) the GUI
falls back to Python class variable defaults — which no longer match how the app looks
after months of tuning.  This plan makes the "factory reset" state match the current
configured look by:

1. Introducing `state/defaults.yaml` — a snapshot of `current.yaml` with transient
   fields (search queries, selected node) zeroed out.
2. Teaching `_load_state()` to fall back to `defaults.yaml` when `current.yaml` is
   missing.
3. Writing a `scripts/ai-only-scripts/snapshot-gui-defaults/run` helper so the user
   can re-snapshot any time with one command.

## Context

Key findings from codebase exploration:

- **`_load_state()`** (`homelab_gui.py` line 743): reads `STATE_DIR/current.yaml`,
  returns `{}` on any error — no existing fallback.
- **`_load_saved_menu()`** (~line 5402): calls `_load_state()` and uses the result to
  set ~66 state vars; empty dict → all vars take Python class defaults.
- **`STATE_DIR`**: resolved at startup from env var / path relative to repo root
  (find the exact definition in the file with `grep -n STATE_DIR homelab_gui.py`).
- **Transient keys** (should be zeroed in defaults.yaml, not snapshotted):
  `config_data_search_query`, `unit_file_search_query`, `explorer_search`,
  `unit_params_search`, `selected_node_path`.
- **All other keys** (scalars + filter dicts + provider list): snapshot as-is.
- Current values that differ most noticeably from Python defaults:
  `ui_theme=dark`, `depth_limit=0`, `show_unit_build_status=true`,
  `show_wave_numbers=true`, `auto_select_recent_unit=true`,
  `cy_show_dependencies=true`, `param_wrap_values=true`,
  `wave_show_duration=true`, `wave_show_log_update=true`,
  `object_viewer_mode=waves`, `resizer_drag_width=13`,
  `panel_width_pct=45`, `top_row_height_pct=45`,
  all `appear_s_*` sections open, and `package_filters` with only
  `pwy-home-lab-pkg` visible.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

---

### `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — modify

Change `_load_state()` to fall back to `state/defaults.yaml` when `current.yaml` is
missing (not on parse error — a corrupt current.yaml is a different problem).

**Exact change** — replace:

```python
def _load_state() -> dict:
    """Load state/current.yaml (runtime UI state)."""
    state_file = STATE_DIR / "current.yaml"
    try:
        return yaml.safe_load(state_file.read_text()) or {}
    except Exception:
        return {}
```

with:

```python
def _load_state() -> dict:
    """Load state/current.yaml (runtime UI state).

    Falls back to state/defaults.yaml when current.yaml is absent (first boot,
    fresh clone, wiped container).  A corrupt current.yaml still returns {}.
    """
    state_file = STATE_DIR / "current.yaml"
    defaults_file = STATE_DIR / "defaults.yaml"
    if not state_file.exists() and defaults_file.exists():
        try:
            return yaml.safe_load(defaults_file.read_text()) or {}
        except Exception:
            return {}
    try:
        return yaml.safe_load(state_file.read_text()) or {}
    except Exception:
        return {}
```

---

### `infra/de3-gui-pkg/_application/de3-gui/state/defaults.yaml` — create

A snapshot of `current.yaml` with transient fields zeroed.  Written once by the
snapshot script (see next section); also created here as the authoritative initial
snapshot.

Content (generated from `state/current.yaml` with transient fields cleared):

```yaml
current:
  menu:
    appear_s_controls: true
    appear_s_file: true
    appear_s_infra: true
    appear_s_layout: true
    appear_s_networks: true
    appear_s_params: true
    appear_s_popup: false
    appear_s_terminal: true
    appear_s_theme: true
    appear_s_wave: true
    auto_select_recent_unit: true
    browser_profile: playwright
    config_data_quote_path: false
    config_data_search_query: ''
    cy_color_by_wave: false
    cy_show_dependencies: true
    cy_wheel_sensitivity: 0.3
    depth_limit: 0
    env_filters:
      _none: true
      dev: true
      example: true
    explorer_root: infra
    explorer_search: ''
    file_search_case_sensitive: false
    file_search_smooth_scroll: false
    file_viewer_mode: unit_file
    file_viewer_render_markdown: true
    file_viewer_show_line_numbers: false
    float_file_viewer_open: true
    float_fv_saved_x: ''
    float_fv_saved_y: ''
    float_object_viewer_open: true
    float_ov_saved_x: ''
    float_ov_saved_y: ''
    float_term_saved_x: ''
    float_term_saved_y: ''
    float_terminal_open: true
    floating_panels_mode: false
    hide_provider_underscore_params: false
    hide_special_params: false
    left_view: tree
    object_viewer_mode: waves
    package_filters:
      _none: false
      aws-pkg: false
      azure-pkg: false
      de3-gui-pkg: false
      default-pkg: false
      demo-buckets-example-pkg: false
      gcp-pkg: false
      image-maker-pkg: false
      maas-pkg: false
      mesh-central-pkg: false
      mikrotik-pkg: false
      proxmox-pkg: false
      pwy-home-lab-pkg: true
      unifi-pkg: false
    panel_show_depth: true
    panel_show_merged: true
    panel_show_view_selector: true
    panel_width_pct: 45
    param_wrap_values: true
    providers:
    - provider-name: proxmox
      show: true
    - provider-name: maas
      show: true
    - provider-name: unifi
      show: true
    - provider-name: gcp
      show: true
    - provider-name: aws
      show: true
    - provider-name: azure
      show: true
    - provider-name: 'null'
      show: true
    region_filters:
      _none: true
      eastus: true
      example-lab: true
      pwy-homelab: true
      us-central1: true
      us-east-1: true
    resizer_drag_width: 13
    selected_editor_id: ''
    selected_node_path: ''
    selected_roles: []
    show_full_module_name: false
    show_status_bar: true
    show_unit_build_status: true
    show_unit_popup: false
    show_wave_numbers: true
    terminal_backend: ttyd
    terminal_hide_initial_cmd: true
    top_row_height_pct: 45
    tree_mode: separated
    ui_theme: dark
    unit_file_search_query: ''
    unit_params_search: ''
    unit_status_auto_refresh: false
    unit_status_auto_refresh_secs: 30
    viz_framework: reflex
    wave_filters:
      _none: true
      cloud.k8s: true
      cloud.storage: true
      external.proxmox.isos-and-snippets: true
      hypervisor.proxmox.configure: true
      hypervisor.proxmox.install: true
      hypervisor.proxmox.storage: true
      local.updates: true
      maas.lifecycle.allocated: true
      maas.lifecycle.commissioning: true
      maas.lifecycle.deployed: true
      maas.lifecycle.deploying: true
      maas.lifecycle.new: true
      maas.lifecycle.ready: true
      maas.machine.config.networking: true
      maas.machine.config.power: true
      maas.servers.all: true
      maas.test.proxmox-vms: true
      network.mikrotik: true
      network.unifi: true
      network.unifi.validate-config: true
      vms.proxmox.custom-images.image-maker: true
      vms.proxmox.from-kairos: true
      vms.proxmox.from-packer: true
      vms.proxmox.from-web.rocky: true
      vms.proxmox.from-web.ubuntu: true
      vms.proxmox.utility.mesh-central: true
    wave_highlight_recent: true
    wave_show_age: false
    wave_show_duration: true
    wave_show_end_time: false
    wave_show_log_update: true
    wave_show_start_time: false
```

---

### `scripts/ai-only-scripts/snapshot-gui-defaults/run` — create

Re-snapshot `defaults.yaml` from the live `current.yaml`, zeroing transient fields.
Run this whenever you want to "freeze" the current GUI look as the new defaults.

```bash
#!/usr/bin/env bash
set -euo pipefail
GIT_ROOT="$(git rev-parse --show-toplevel)"
source "${GIT_ROOT}/set_env.sh"

CURRENT="${GIT_ROOT}/infra/de3-gui-pkg/_application/de3-gui/state/current.yaml"
DEFAULTS="${GIT_ROOT}/infra/de3-gui-pkg/_application/de3-gui/state/defaults.yaml"

if [[ ! -f "${CURRENT}" ]]; then
  echo "ERROR: ${CURRENT} does not exist — start the GUI at least once first." >&2
  exit 1
fi

python3 - <<'PYEOF'
import sys, yaml
from pathlib import Path

git_root = Path(sys.argv[0]).resolve().parent.parent.parent.parent
# Re-resolve from env since we need the GUI state dir
import os
current_path = Path(os.environ.get("_STACK_DIR", git_root)) / "infra/de3-gui-pkg/_application/de3-gui/state/current.yaml"
defaults_path = current_path.parent / "defaults.yaml"

TRANSIENT = {
    "config_data_search_query",
    "unit_file_search_query",
    "explorer_search",
    "unit_params_search",
    "selected_node_path",
}

data = yaml.safe_load(current_path.read_text()) or {}
menu = data.get("current", {}).get("menu", {})
for key in TRANSIENT:
    menu[key] = ""
data["current"]["menu"] = menu

defaults_path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False))
print(f"Wrote {defaults_path}")
PYEOF
```

**Note:** The script uses Python inline to safely handle YAML round-tripping. The
`sys.argv[0]` trick is unreliable inside heredocs — instead the script reads `_STACK_DIR`
from the sourced env. Fix the python path resolution: replace the `sys.argv` approach
with a direct reference to the known path based on `GIT_ROOT`:

```bash
#!/usr/bin/env bash
set -euo pipefail
GIT_ROOT="$(git rev-parse --show-toplevel)"
source "${GIT_ROOT}/set_env.sh"

STATE_DIR="${GIT_ROOT}/infra/de3-gui-pkg/_application/de3-gui/state"
CURRENT="${STATE_DIR}/current.yaml"
DEFAULTS="${STATE_DIR}/defaults.yaml"

if [[ ! -f "${CURRENT}" ]]; then
  echo "ERROR: ${CURRENT} does not exist — start the GUI at least once first." >&2
  exit 1
fi

python3 - "${CURRENT}" "${DEFAULTS}" <<'PYEOF'
import sys, yaml
from pathlib import Path

current_path  = Path(sys.argv[1])
defaults_path = Path(sys.argv[2])

TRANSIENT = {
    "config_data_search_query",
    "unit_file_search_query",
    "explorer_search",
    "unit_params_search",
    "selected_node_path",
}

data = yaml.safe_load(current_path.read_text()) or {}
menu = data.get("current", {}).get("menu", {})
for key in TRANSIENT:
    menu[key] = ""
data["current"]["menu"] = menu

defaults_path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False))
print(f"Wrote {defaults_path}")
PYEOF
```

> Use the second (corrected) version above when writing the actual file.

## Execution Order

1. Modify `_load_state()` in `homelab_gui.py` to add the `defaults.yaml` fallback.
2. Create `state/defaults.yaml` with the content above.
3. Create `scripts/ai-only-scripts/snapshot-gui-defaults/run` (executable).
4. Verify: rename `state/current.yaml` → `state/current.yaml.bak`, restart the GUI,
   confirm it loads with the expected look, then restore the backup.

## Verification

```bash
# 1. Confirm syntax is OK
python3 -c "import ast; ast.parse(open('homelab_gui/homelab_gui.py').read()); print('OK')"

# 2. Confirm defaults.yaml parses cleanly
python3 -c "import yaml; d=yaml.safe_load(open('state/defaults.yaml').read()); print(len(d['current']['menu']), 'keys')"

# 3. Simulate missing current.yaml
mv state/current.yaml state/current.yaml.bak
# restart GUI — should load defaults.yaml and look identical
# restore
mv state/current.yaml.bak state/current.yaml

# 4. Test snapshot script
./scripts/ai-only-scripts/snapshot-gui-defaults/run
```
