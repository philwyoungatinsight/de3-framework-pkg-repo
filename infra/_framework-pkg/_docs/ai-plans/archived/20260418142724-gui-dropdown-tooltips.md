# Plan: Add Tooltips to All Infra Panel Dropdown Options

## Objective

Add hover tooltips to every option in the four infra panel dropdowns (Infra, Appearance,
Panels, Help). Currently none of the menu items have tooltips — only the dropdown trigger
buttons do. This makes the controls self-documenting without requiring the user to click
and read docs.

## Context

- All four dropdown trigger buttons already use the HTML `title=` attribute for native
  browser tooltips (consistent, works in all browsers).
- The `_appearance_menu_item()` helper (line 13837) renders an `rx.hstack` with a checkbox
  and label — no tooltip parameter. This is used by both `appearance_menu()` and
  `panels_menu()`.
- `help_menu()` and `_explorer_root_selector()` use `rx.dropdown_menu.item()` directly
  — tooltips go on `title=` prop of the item.
- `rx.tooltip()` is NOT used here: it closes dropdowns mid-interaction. `title=` (native
  browser tooltip) is the correct pattern, consistent with the rest of the file.
- Two items already have `title=` on sub-elements (Zoom Speed, Drag Width sliders) —
  leave those untouched.
- The Light/Dark theme buttons and Refresh/Open-in buttons already have `title=` — leave
  untouched.
- The Terminal Backend `rx.select` already has `title=` — leave untouched.
- The Auto-refresh interval `rx.select` already has `title=` — leave untouched.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — modify

**Change 1: `_appearance_menu_item()` — add optional `tooltip` parameter (line 13837)**

Add `tooltip: str = ""` to the signature and apply `title=tooltip` to the `rx.hstack`
only when non-empty (use `**({"title": tooltip} if tooltip else {})` to keep the call
clean when tooltip is absent).

Current signature (line 13837):
```python
def _appearance_menu_item(label: str, checked: rx.Var, on_change, on_row_click) -> rx.Component:
```

New signature:
```python
def _appearance_menu_item(label: str, checked: rx.Var, on_change, on_row_click, tooltip: str = "") -> rx.Component:
```

Current rx.hstack (line 13845):
```python
    return rx.hstack(
        rx.checkbox(checked=checked, on_change=on_change, size="1"),
        rx.text(label, font_size="13px", on_click=on_row_click,
                cursor="pointer", flex="1"),
        align="center",
        spacing="2",
        padding_y="4px",
        padding_x="6px",
        border_radius="4px",
        width="100%",
        _hover={"background": "var(--gui-hover-soft)"},
    )
```

New rx.hstack (add `title=tooltip` if tooltip is non-empty):
```python
    return rx.hstack(
        rx.checkbox(checked=checked, on_change=on_change, size="1"),
        rx.text(label, font_size="13px", on_click=on_row_click,
                cursor="pointer", flex="1"),
        align="center",
        spacing="2",
        padding_y="4px",
        padding_x="6px",
        border_radius="4px",
        width="100%",
        _hover={"background": "var(--gui-hover-soft)"},
        **({"title": tooltip} if tooltip else {}),
    )
```

---

**Change 2: `_explorer_root_selector()` — add `title=` to each `rx.dropdown_menu.item()` (lines 13560–13575)**

```python
rx.dropdown_menu.item(
    "Infra",
    on_click=AppState.set_explorer_root("infra"),
    title="Browse the infrastructure tree: Terragrunt units organised by package and wave",
),
rx.dropdown_menu.item(
    "Modules",
    on_click=AppState.set_explorer_root("modules"),
    title="Browse Terraform module definitions: reusable building blocks shared across units",
),
rx.dropdown_menu.item(
    "Packages",
    on_click=AppState.set_explorer_root("packages"),
    title="Browse packages: top-level groupings of infrastructure (e.g. maas-pkg, de3-gui-pkg)",
),
rx.dropdown_menu.item(
    "Ansible Inventory",
    on_click=AppState.set_explorer_root("ansible_inventory"),
    title="Browse the dynamic Ansible inventory: hosts grouped by role and wave",
),
```

---

**Change 3: `panels_menu()` — add `tooltip=` to all four `_appearance_menu_item()` calls (lines 13869–13893)**

```python
_appearance_menu_item(
    "Unit detail popup",
    AppState.show_unit_popup,
    AppState.toggle_show_unit_popup,
    AppState.flip_show_unit_popup,
    tooltip="Show a detail panel when clicking a unit — works in both layout modes",
),
_appearance_menu_item(
    "File viewer",
    AppState.float_file_viewer_open,
    AppState.toggle_float_file_viewer,
    AppState.flip_float_file_viewer,
    tooltip="Open a floating file viewer panel (requires Floating panels mode)",
),
_appearance_menu_item(
    "Terminal",
    AppState.float_terminal_open,
    AppState.toggle_float_terminal,
    AppState.flip_float_terminal,
    tooltip="Open a floating terminal panel (requires Floating panels mode)",
),
_appearance_menu_item(
    "Object viewer",
    AppState.float_object_viewer_open,
    AppState.toggle_float_object_viewer,
    AppState.flip_float_object_viewer,
    tooltip="Open a floating object/JSON viewer panel (requires Floating panels mode)",
),
```

---

**Change 4: `help_menu()` — add `title=` to each `rx.dropdown_menu.item()` (lines 13928–13958)**

```python
rx.dropdown_menu.item(
    rx.hstack(rx.icon("book-open", size=14), rx.text("Docs (GUI)"),
              spacing="2", align="center"),
    on_click=AppState.open_docs,
    title="Open the GUI user documentation in a new browser tab",
),
rx.dropdown_menu.item(
    rx.hstack(rx.icon("book-open", size=14), rx.text("Docs (Engine)"),
              spacing="2", align="center"),
    on_click=AppState.open_docs_engine,
    title="Open the infrastructure engine documentation in a new browser tab",
),
rx.dropdown_menu.item(
    rx.hstack(rx.icon("book-open", size=14), rx.text("Topics"),
              spacing="2", align="center"),
    on_click=AppState.open_docs_topics,
    title="Browse documentation topics for the infrastructure framework",
),
rx.dropdown_menu.item(
    rx.hstack(rx.icon("book-open", size=14), rx.text("Scripts"),
              spacing="2", align="center"),
    on_click=AppState.open_docs_scripts,
    title="Browse available scripts: wave scripts, Terragrunt hooks, and human-only utilities",
),
rx.dropdown_menu.separator(),
rx.dropdown_menu.item(
    rx.hstack(rx.icon("info", size=14), rx.text("About"),
              spacing="2", align="center"),
    on_click=AppState.open_help_about,
    title="Show app version, Python/Reflex versions, and current configuration",
),
rx.dropdown_menu.item(
    rx.hstack(rx.icon("scroll-text", size=14), rx.text("License"),
              spacing="2", align="center"),
    on_click=AppState.open_help_license,
    title="View the software license",
),
```

---

**Change 5: `appearance_menu()` — add `tooltip=` to all `_appearance_menu_item()` calls**

Tooltip strings by section (pass as `tooltip=` positional-last kwarg):

**Show in controls bar (lines ~14019–14036):**
- View selector: `"Show the Infra/Modules/Packages/Ansible Inventory switcher in the top bar"`
- Show merged: `"Show the merged-view toggle in the top bar (combines applied + to-apply units)"`
- Depth: `"Show the tree depth limit slider in the top bar"`

**Infra tree (lines ~14043–14059):**
- Show full module name: `"Show the full Terraform module path on each tree node instead of the short display name"`
- Show wave numbers: `"Prefix each tree node with its wave number (e.g. [12] machine-name)"`
- Show build status: `"Colour tree nodes by their last known build state (applied / destroyed / unknown)"`

**Wave panel (lines ~14157–14192):**
- Start time: `"Show the wave start time column in the wave panel"`
- End time: `"Show the wave end time column in the wave panel"`
- Duration: `"Show the wave run duration column in the wave panel"`
- Age: `"Show how long ago the wave last ran in the wave panel"`
- Last Update: `"Show the time of the most recent log-file write for each wave"`
- Highlight recent wave: `"Highlight the most-recently-run wave with a coloured border"`

**File viewer (lines ~14199–14210):**
- Render markdown files: `"Render .md files as formatted HTML instead of showing raw text"`
- Show line numbers: `"Show line numbers in the file viewer code pane"`

**Terminal (lines ~14217–14222):**
- Hide auto-run commands: `"Hide the initial auto-run command from the terminal display (the command still runs)"`

**Params panel (lines ~14273–14278):**
- Wrap long values: `"Wrap long parameter values to multiple lines instead of truncating with ellipsis"`

**Nested networks (lines ~14285–14295):**
- Show dependency arrows: `"Draw directed arrows between nodes to show Terraform dependencies"`
- Color nodes by wave: `"Colour each node in the dependency graph by its wave number"`

**Layout (lines ~14338–14349):**
- Status bar: `"Show the status bar at the bottom of the app with build state and GCS sync info"`
- Floating panels mode: `"Switch to draggable floating panels for file viewer, terminal, and object viewer"`

## Execution Order

1. Update `_appearance_menu_item()` signature and body (Change 1) — must be done first
   so all callers can immediately start passing the new `tooltip` kwarg.
2. Update `_explorer_root_selector()` (Change 2)
3. Update `panels_menu()` (Change 3)
4. Update `help_menu()` (Change 4)
5. Update `appearance_menu()` (Change 5) — many calls; do section by section

## Verification

```bash
# Confirm the helper signature now has tooltip param
grep -n "def _appearance_menu_item" infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py

# Confirm tooltip kwarg count in appearance_menu (expect ~16)
grep -c 'tooltip=' infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py

# Confirm title= added to dropdown items in help and infra menus
grep -A2 'open_docs\|open_help\|set_explorer_root' infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py | grep title=
```

Start the dev server and hover over each menu item to confirm tooltips appear.
