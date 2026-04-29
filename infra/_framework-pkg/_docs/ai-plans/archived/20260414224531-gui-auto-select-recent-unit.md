# Plan: Auto-Select Recent Unit (Appearance Toggle)

## Objective

Add an "Auto-select recent unit" toggle to the Appearance menu's new "Folder view behaviour"
section (paralleling the existing "Wave panel behaviour → Highlight recent wave" toggle). When
enabled, the tree auto-selects and highlights the unit whose apply most recently completed —
driven by the existing `local_state_watcher` background loop that already detects changes.

## Context

### Existing analogous feature

`wave_highlight_recent` / `recent_wave_name` (line ~3762) — toggled in Appearance → "Wave panel
behaviour". The `poll_wave_status` handler sets `recent_wave_name` to the most-recently-running
wave; the table row uses it for background colour. We mirror this pattern for the unit tree.

### Unit change detection

`local_state_watcher` (line 8037) already detects unit applies via three tiers:
- **Tier 1** (~line 8156–8210): `.terragrunt-cache/*/terraform.tfstate` mtime changes → GCS
  fetch → writes `updates: dict[str, str]` and calls `_write_unit_state(yaml_updates)` where
  `yaml_updates` includes `"last_apply_at": now_iso`.
- **Tier 3** (~line 8216–8254): exit-code files `/tmp/homelab_gui_apply_*.exit` → same pattern.
- **Auto-refresh path** (~line 8095–8124): reads unit-state.yaml when mtime changes or interval
  elapses → sets `auto_statuses` and merges into `unit_build_statuses`.

All three paths run inside the background task `local_state_watcher` and mutate state via
`async with self:`.

### Unit selection

`select_node(path)` (line 5661) is the canonical "select a unit" handler. It:
1. Resets file editor state
2. Sets `selected_node_path`, `active_provider_tab`, `unit_hcl_path`
3. Loads HCL content into `hcl_content` / `hcl_file_path`

`click_node(path)` (line 6333) adds expand/collapse on top of that.

For auto-select we need to expand **ancestors** (not descendants) so the node is visible, then
select it. This is different from `click_node` which expands the subtree below.

### Tree visibility rule

A node at `a/b/c/d` is visible only when `a`, `a/b`, and `a/b/c` are all in `expanded_paths`
(or `merged_expanded_paths` for merged mode). Auto-select must add all ancestor prefixes.

### Persistence

All menu state is saved via `_save_current_config()` → `_schedule_config_write()` (line 5055)
and restored in `on_load()` (line 5122). Pattern for new bool: add to the dict passed to
`_schedule_config_write` and restore with `bool(saved_menu.get("key", default))` in `on_load`.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — modify

Six distinct changes, all in the same file. Listed by execution order below.

---

#### Change 1 — State variables (near line 3762)

After:
```python
    wave_highlight_recent:    bool = True   # highlight the most recently updated wave row
    recent_wave_name:         str  = ""     # wave name whose log was updated within last N secs ...
```

Add:
```python
    auto_select_recent_unit:  bool = False  # auto-select the unit most recently changed by an apply
    recent_unit_path:         str  = ""     # path of the unit most recently seen by local_state_watcher
```

---

#### Change 2 — `_apply_auto_select` helper (after `select_node`, near line 5694)

This is a plain helper method (not a Reflex event, so underscore prefix is fine). It is called
ONLY from inside `async with self:` blocks in `local_state_watcher`, where `self` is the locked
AppState instance.

Add after `select_node` (and before `set_ui_theme`):

```python
    def _apply_auto_select(self, unit_path: str):
        """Auto-select a unit in the tree: expand ancestors so it is visible, load HCL.

        Called from local_state_watcher (inside async with self:) when
        auto_select_recent_unit is True and a unit status changes.
        Does NOT toggle expand/collapse like click_node — it only opens ancestors.
        """
        if not unit_path:
            return
        self.recent_unit_path = unit_path
        self.selected_node_path = unit_path
        self.active_provider_tab = ""
        self.unit_hcl_path = _read_hcl_file(unit_path)[1]

        # Expand all ancestor prefixes so the node is visible in the tree.
        parts = unit_path.split("/")
        ancestors = {"/".join(parts[:i]) for i in range(1, len(parts) + 1)}
        self.expanded_paths        = list(set(self.expanded_paths)        | ancestors)
        self.merged_expanded_paths = list(set(self.merged_expanded_paths) | ancestors)

        # Load HCL content for the right panel.
        if self.tree_mode == "merged":
            providers = _get_hcl_providers_for_merged(unit_path)
            first = providers[0] if providers else ""
            self.file_viewer_provider = first
            self.hcl_content, self.hcl_file_path = _read_hcl_file_for_merged(unit_path, first)
        else:
            self.file_viewer_provider = ""
            self.hcl_content, self.hcl_file_path = _read_hcl_file(unit_path)
```

---

#### Change 3 — Toggle event handlers (after `flip_wave_highlight_recent`, near line 5545)

After:
```python
    def flip_wave_highlight_recent(self):
        self.wave_highlight_recent = not self.wave_highlight_recent
        self._save_current_config()
```

Add:
```python
    def toggle_auto_select_recent_unit(self, checked: bool):
        self.auto_select_recent_unit = checked
        self._save_current_config()

    def flip_auto_select_recent_unit(self):
        self.auto_select_recent_unit = not self.auto_select_recent_unit
        self._save_current_config()
```

---

#### Change 4 — Persistence: `_save_current_config` (near line 5074)

After:
```python
            "wave_highlight_recent":        self.wave_highlight_recent,
```

Add:
```python
            "auto_select_recent_unit":      self.auto_select_recent_unit,
```

---

#### Change 5 — Persistence: `on_load` restore (near line 5172)

After:
```python
        self.wave_highlight_recent     = bool(saved_menu.get("wave_highlight_recent",     True))
```

Add:
```python
        self.auto_select_recent_unit   = bool(saved_menu.get("auto_select_recent_unit",   False))
```

---

#### Change 6 — `local_state_watcher`: hook auto-select into all three update paths

**6a — Tier 1 updates** (after `async with self:` block at line ~8199, which sets
`self.unit_build_statuses`):

The existing block is:
```python
                    if updates:
                        async with self:
                            self.unit_build_statuses = {**self.unit_build_statuses, **updates}
```

Change to:
```python
                    if updates:
                        async with self:
                            self.unit_build_statuses = {**self.unit_build_statuses, **updates}
                            if self.auto_select_recent_unit:
                                # Pick the unit with the most recent last_apply_at from the
                                # yaml_updates we're about to write (all share the same now_iso,
                                # so just pick any key — typically one unit at a time).
                                most_recent = next(iter(updates))
                                self._apply_auto_select(most_recent)
```

Note: `yaml_updates` is computed AFTER this block, so we use `updates` (same keys). Single unit
applies are by far the common case; when multiple change simultaneously we pick arbitrarily.

**6b — Tier 3 exit files** (after `async with self:` block at line ~8243, which sets
`self.unit_build_statuses` from `exit_updates`):

The existing block is:
```python
                if exit_updates:
                    async with self:
                        self.unit_build_statuses = {**self.unit_build_statuses, **exit_updates}
```

Change to:
```python
                if exit_updates:
                    async with self:
                        self.unit_build_statuses = {**self.unit_build_statuses, **exit_updates}
                        if self.auto_select_recent_unit:
                            most_recent = next(iter(exit_updates))
                            self._apply_auto_select(most_recent)
```

**6c — Auto-refresh path** (in the `mtime_changed or interval_elapsed` block, after
`async with self:` at line ~8112 which sets `unit_build_statuses` from `auto_statuses`):

The existing block is:
```python
                            if unit_state:
                                auto_statuses = {
                                    path: entry["status"]
                                    for path, entry in unit_state.items()
                                    if "status" in entry
                                }
                                async with self:
                                    self.unit_build_statuses = {
                                        **self.unit_build_statuses, **auto_statuses
                                    }
```

Change to:
```python
                            if unit_state:
                                auto_statuses = {
                                    path: entry["status"]
                                    for path, entry in unit_state.items()
                                    if "status" in entry
                                }
                                async with self:
                                    self.unit_build_statuses = {
                                        **self.unit_build_statuses, **auto_statuses
                                    }
                                    if self.auto_select_recent_unit and mtime_changed:
                                        # Pick the unit with the most recent last_apply_at.
                                        best = max(
                                            (p for p in unit_state if "last_apply_at" in unit_state[p]),
                                            key=lambda p: unit_state[p]["last_apply_at"],
                                            default="",
                                        )
                                        if best:
                                            self._apply_auto_select(best)
```

Only trigger on `mtime_changed` (not `interval_elapsed`) to avoid re-selecting on every
auto-refresh poll when no new apply has happened.

---

#### Change 7 — Appearance menu: new "Folder view behaviour" section

In `appearance_menu()`, the current structure ends the "Folder view" section with:
```python
                spacing="0",
                padding="4px",
            ),
            rx.separator(width="100%"),
            rx.text(
                "Wave panel columns",
```

Insert a new "Folder view behaviour" section between the "Folder view" vstack end and the
"Wave panel columns" separator:

```python
            rx.separator(width="100%"),
            rx.text(
                "Folder view behaviour",
                font_size="11px",
                font_weight="600",
                color="var(--gui-text-muted)",
                text_transform="uppercase",
                letter_spacing="0.06em",
                padding_x="6px",
                padding_top="6px",
                padding_bottom="4px",
            ),
            rx.vstack(
                _appearance_menu_item(
                    "Auto-select recent unit",
                    AppState.auto_select_recent_unit,
                    AppState.toggle_auto_select_recent_unit,
                    AppState.flip_auto_select_recent_unit,
                ),
                spacing="0",
                padding="4px",
            ),
```

Then continue with the existing `rx.separator(width="100%")` before "Wave panel columns".

## Execution Order

1. **State variables** (Change 1) — define vars before any handler references them
2. **`_apply_auto_select` helper** (Change 2) — define helper before it's called
3. **Toggle handlers** (Change 3) — event handlers that toggle the bool
4. **`_save_current_config`** (Change 4) — persist the new var
5. **`on_load`** (Change 5) — restore on page load
6. **`local_state_watcher` hooks** (Change 6a, 6b, 6c) — wire auto-select into change detection
7. **Appearance menu** (Change 7) — UI toggle visible to user

All changes are in `homelab_gui.py`. Read the file in relevant sections before each edit to
confirm exact surrounding context (line numbers may drift in a 15k-line file).

## Verification

1. Start the GUI: `cd infra/de3-gui-pkg/_application/de3-gui && reflex run`
2. Open Appearance menu → confirm "Folder view behaviour" section appears with "Auto-select
   recent unit" checkbox
3. Enable the toggle → confirm it persists across page reload
4. Run `terragrunt apply` on any unit; within one `local_state_watcher` poll cycle (≤8s in
   normal mode, ≤2s in accelerated mode) the unit should be selected in the tree and its HCL
   loaded in the right panel
5. Disable the toggle → confirm manual clicks work normally and no auto-selection occurs
