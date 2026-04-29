# Plan: GUI — Refactor Menu Update

**File:** `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`

---

## Goals

1. Rename the context-menu group "Edit" → "Refactor"
2. Change "Rename…" menu item to "Rename" (no ellipsis)
3. Replace the single "Refactor (move / copy)…" context menu item with three direct-action items: **Move**, **Copy**, **Delete** — each opens the refactor panel pre-set to that operation
4. Remove the old standalone "Remove unit and config block…" and "Remove unit and config block… (recursive)" context menu items (Delete is now handled by the refactor panel)
5. Update the refactor floating-panel title to **"Refactor (units and config recursively)"**
6. Add **Delete** as a third operation in the refactor panel's operation toggle
7. Hide the Destination input when Delete is selected (no destination needed)
8. Make the Execute button enabled without a destination when Delete is selected
9. Wire up the Delete execution path to reuse the existing recursive-delete backend
10. Add tooltips to all controls in the refactor panel

---

## Files to Modify

| File | Sections |
|------|----------|
| `homelab_gui/homelab_gui.py` | Context menu items (~line 10078–10095), group_labels (~line 10144–10154), dispatch_action (~line 10260–10261), `begin_refactor` (~line 7908), `run_refactor_preview` (~line 8054), `run_refactor_execute` (~line 8106), `_refactor_panel` (~line 14921), `float_refactor_panel` (~line 16596) |

---

## Step-by-Step Changes

### 1. Context menu group label (line ~10146)

```python
# Before
"edit": "Edit",
# After
"edit": "Refactor",
```

### 2. Rename menu item (line ~10081)

```python
# Before
"label": "Rename…",
# After
"label": "Rename",
```

### 3. Replace context menu refactor + delete items (lines ~10083–10095)

Remove:
```python
extra_actions.append({
    "group": "edit", "id": "refactor_node",
    "label": "Refactor (move / copy)…", "action_type": "begin_refactor", "value": path,
})
if has_tg:
    extra_actions.append({
        "group": "edit", "id": "remove_unit",
        "label": "Remove unit and config block…", "action_type": "begin_delete_file", "value": path,
    })
extra_actions.append({
    "group": "edit", "id": "remove_unit_recursive",
    "label": "Remove unit and config block… (recursive)", "action_type": "begin_delete_recursive", "value": path,
})
```

Replace with:
```python
extra_actions.append({
    "group": "edit", "id": "refactor_move",
    "label": "Move", "action_type": "begin_refactor_move", "value": path,
})
extra_actions.append({
    "group": "edit", "id": "refactor_copy",
    "label": "Copy", "action_type": "begin_refactor_copy", "value": path,
})
extra_actions.append({
    "group": "edit", "id": "refactor_delete",
    "label": "Delete", "action_type": "begin_refactor_delete", "value": path,
})
```

### 4. `dispatch_action` — add three new action_types (line ~10260)

Replace:
```python
elif action_type == "begin_refactor":
    return self.begin_refactor(value)
```

With:
```python
elif action_type == "begin_refactor":
    return self.begin_refactor(value)
elif action_type == "begin_refactor_move":
    return self.begin_refactor(value, operation="move")
elif action_type == "begin_refactor_copy":
    return self.begin_refactor(value, operation="copy")
elif action_type == "begin_refactor_delete":
    return self.begin_refactor(value, operation="delete")
```

Also remove the now-unused dispatch routes for `begin_delete_file` and `begin_delete_recursive` **only if no other context menu items reference them**. (Check: `begin_delete_file` is used by the `has_tg` branch we're removing; `begin_delete_recursive` ditto — both can be removed from dispatch.)

### 5. `begin_refactor` — accept `operation` parameter (line ~7908)

```python
# Before
def begin_refactor(self, path: str):
    self.refactor_src_path = path
    self.refactor_dst_path = ""
    ...
    self.float_refactor_open = True
    return [rx.call_script(self._WAVE_POLL_STOP_JS), AppState.init_float_refactor]

# After
def begin_refactor(self, path: str, operation: str = "move"):
    self.refactor_src_path = path
    self.refactor_operation = operation
    self.refactor_dst_path = ""
    ...
    self.float_refactor_open = True
    return [rx.call_script(self._WAVE_POLL_STOP_JS), AppState.init_float_refactor]
```

### 6. `run_refactor_preview` — skip preview for delete (line ~8054)

At the top of the preview handler, add a short-circuit when `op == "delete"`:

```python
if op == "delete":
    async with self:
        # Show a count of what will be deleted using a dry-run of the delete path
        self.refactor_preview_result = {"units_found": "?"}
        self.refactor_error = "Preview not available for Delete — click Execute to confirm deletion."
        self.refactor_running = False
    return
```

### 7. `run_refactor_execute` — handle delete (line ~8106)

After capturing `op`, add a branch before the `if not dst` guard:

```python
if op == "delete":
    # Reuse the existing recursive-delete backend
    async with self:
        self.refactor_running = False
    # Delegate: set delete state fields and call confirm_delete
    async with self:
        self.delete_pending_path = src
        self.delete_pending_mode = "recursive"
    return AppState.confirm_delete
```

This reuses the existing `confirm_delete` event handler that already handles:
- `shutil.rmtree` of the unit directory
- Removal of config block from YAML files
- Reload of the infra tree

Also update the `if not dst` guard so it does NOT apply when `op == "delete"`:

```python
if op != "delete" and not dst:
    async with self:
        self.refactor_error = "Destination path is required."
        self.refactor_running = False
    return
```

### 8. `float_refactor_panel` — update title (line ~16602)

```python
# Before
rx.text("Refactor", font_size="12px", ...)

# After
rx.text("Refactor (units and config recursively)", font_size="12px", ...)
```

### 9. `_refactor_panel` — add Delete button to operation selector (line ~14999)

```python
# After the existing Copy button, add:
rx.button(
    "Delete",
    size="1",
    variant=rx.cond(AppState.refactor_operation == "delete", "solid", "soft"),
    color_scheme="red",
    on_click=AppState.set_refactor_operation("delete"),
    title="Delete this unit tree and all config keys recursively",
),
```

### 10. `_refactor_panel` — hide destination when Delete selected (line ~15035)

Wrap the destination vstack in `rx.cond`:

```python
rx.cond(
    AppState.refactor_operation != "delete",
    rx.vstack(
        rx.text("Destination:", font_size=_fs, color=_dim,
                title="Enter or click on a destination path"),
        rx.input(
            placeholder="<pkg>/_stack/…",
            value=AppState.refactor_dst_path,
            on_change=AppState.set_refactor_dst_path,
            font_size="11px",
            font_family=_mono,
            width="100%",
            title="Enter or click on a destination path",
        ),
        spacing="1", align_items="start", width="100%",
    ),
    rx.box(),
),
```

### 11. `_refactor_panel` — fix Execute button disabled logic

```python
# Before
disabled=rx.cond(
    AppState.refactor_running,
    True,
    AppState.refactor_dst_path == "",
),

# After
disabled=rx.cond(
    AppState.refactor_running,
    True,
    rx.cond(
        AppState.refactor_operation == "delete",
        False,
        AppState.refactor_dst_path == "",
    ),
),
```

### 12. `_refactor_panel` — add tooltips to all controls

Add `title=` props throughout `_refactor_panel()`:

| Control | `title` value |
|---------|---------------|
| "Operation:" label | `"Select the refactor operation to perform"` |
| Move button | `"Move this unit tree and all config keys to a new path"` |
| Copy button | `"Copy this unit tree and all config keys to a new path"` |
| Delete button | `"Delete this unit tree and all config keys recursively"` |
| "Source:" label | `"The unit path being refactored"` |
| Source path text box | `"Source path (read-only)"` |
| "Destination:" label | `"Enter or click on a destination path"` |
| Destination input | `"Enter or click on a destination path"` |
| Preview button | `"Dry-run: show what will change without making any modifications"` |
| Execute button | `"Apply the selected operation — this cannot be undone"` |
| Clear button | `"Clear the preview/result output"` |

---

## Open Questions

None — all changes are contained within `homelab_gui.py`. No new state fields are needed; `refactor_operation` already accepts arbitrary strings.

---

## Testing

After making changes, restart the GUI dev server and verify:

1. Right-click a node → context menu shows "Refactor" group with "Rename", "Move", "Copy", "Delete"
2. Clicking Move/Copy opens refactor panel pre-set to that operation with destination input visible
3. Clicking Delete opens refactor panel pre-set to Delete with destination input hidden
4. Refactor panel title reads "Refactor (units and config recursively)"
5. Operation toggle shows Move / Copy / Delete buttons; active button is highlighted
6. Execute with Delete selected triggers deletion and tree reload
7. Hovering over controls shows appropriate tooltips
