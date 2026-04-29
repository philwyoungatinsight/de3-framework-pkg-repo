# Plan: GUI Floating Panels Mode + Appearance Menu Grouping

## Objective

Two improvements:
1. **Floating panels mode**: a new mode where only the infra tree stays in the layout;
   file viewer, terminal, and object viewer become independent draggable/resizable windows.
2. **Appearance menu accordion**: the flat scrollable appearance menu is reorganised into
   10 collapsible accordion sections so it fits on screen.

---

## Context

### Current layout (from `index()`, line ~15461)

```
┌─────────────────────┬──────────────────────────┐
│  left_panel()       │  bottom_left_panel()      │  ← top row
│  (infra tree)       │  (file viewer)            │
├─────────────────────┼──────────────────────────┤
│  bottom_right_panel()│  top_right_panel()       │  ← bottom row
│  (terminal/browser) │  (object viewer)          │
└─────────────────────┴──────────────────────────┘
```

**Panel function names** (confusing but correct, do not rename):
| DOM position | Function | Content |
|---|---|---|
| Top-left | `left_panel()` | Infra tree explorer |
| Top-right | `bottom_left_panel()` | File viewer |
| Bottom-left | `bottom_right_panel()` | Terminal / browser |
| Bottom-right | `top_right_panel()` | Object viewer (params, waves, refactor) |

### Reference patterns
- **Floating popup**: `hover_popup_window()` — `position:fixed`, CSS vars `--popup-x/y`,
  `_positionSet` guard for initial snap, `_dragInstalled` guard for drag listeners.
  All three new floating panels must follow this exact pattern.
- **`_appearance_menu_item`**: checkbox + label row; separate `on_change` / `on_row_click`
  to prevent double-fire. Reused in the new `panels_menu()`.

### Design decisions (all answered)
- Q1 **Infra tree width in floating mode**: `min-width: left_panel_width_style; width: max-content`
  so tree expands to fit long folder names but doesn't shrink below current width.
- Q2 **Floating panel controls**: new **"Panels ▾"** menu in navbar, next to Appearance.
  Three checkboxes (file viewer, terminal, object viewer). ✕ button unchecks its checkbox.
- Q3 **Appearance menu grouping**: **accordion sections** (individual bool state vars per
  section; Reflex `rx.cond` collapses/expands bodies). Persisted in config.
- Q4 **Default positions**: **stack near viewport centre** with 30 px offsets:
  file viewer at `(cx-300, cy-220)`, terminal at `(cx-270, cy-190)`,
  object viewer at `(cx-240, cy-160)` where `cx=vw/2, cy=vh/2`.
- Q5 **Position persistence**: yes — saved to `state/current.yaml`. Positions saved when
  panel is closed with ✕. Restored via state vars passed into the init JS.

---

## Open Questions

None — ready to proceed.

---

## Files to Create / Modify

### `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — modify

#### A. New state vars (add near hover popup vars, ~line 3882)

```python
# ── Floating panels mode ─────────────────────────────────────────────
floating_panels_mode:      bool = False   # persisted
float_file_viewer_open:    bool = True    # persisted; Panels menu checkbox
float_terminal_open:       bool = True
float_object_viewer_open:  bool = True
# Saved positions — restored to CSS vars on init so panels reappear where left
float_fv_saved_x:  str = ""   # e.g. "480px"  (empty = use default centre calc)
float_fv_saved_y:  str = ""
float_term_saved_x: str = ""
float_term_saved_y: str = ""
float_ov_saved_x:   str = ""
float_ov_saved_y:   str = ""

# ── Appearance menu accordion section open/closed state (persisted) ──
appear_s_controls: bool = True   # "Show in controls bar" — open by default
appear_s_infra:    bool = True   # "Infra tree"
appear_s_wave:     bool = False
appear_s_file:     bool = False
appear_s_popup:    bool = False
appear_s_terminal: bool = False
appear_s_params:   bool = False
appear_s_networks: bool = False
appear_s_layout:   bool = False
appear_s_theme:    bool = False
```

#### B. `_save_current_config` — add to the dict

```python
"floating_panels_mode":     self.floating_panels_mode,
"float_file_viewer_open":   self.float_file_viewer_open,
"float_terminal_open":      self.float_terminal_open,
"float_object_viewer_open": self.float_object_viewer_open,
"float_fv_saved_x":  self.float_fv_saved_x,
"float_fv_saved_y":  self.float_fv_saved_y,
"float_term_saved_x": self.float_term_saved_x,
"float_term_saved_y": self.float_term_saved_y,
"float_ov_saved_x":  self.float_ov_saved_x,
"float_ov_saved_y":  self.float_ov_saved_y,
"appear_s_controls": self.appear_s_controls,
"appear_s_infra":    self.appear_s_infra,
"appear_s_wave":     self.appear_s_wave,
"appear_s_file":     self.appear_s_file,
"appear_s_popup":    self.appear_s_popup,
"appear_s_terminal": self.appear_s_terminal,
"appear_s_params":   self.appear_s_params,
"appear_s_networks": self.appear_s_networks,
"appear_s_layout":   self.appear_s_layout,
"appear_s_theme":    self.appear_s_theme,
```

#### C. `on_load` — restore new vars

Add restoration for all new vars, same pattern as existing vars:
```python
self.floating_panels_mode     = cfg.get("floating_panels_mode", False)
self.float_file_viewer_open   = cfg.get("float_file_viewer_open", True)
self.float_terminal_open      = cfg.get("float_terminal_open", True)
self.float_object_viewer_open = cfg.get("float_object_viewer_open", True)
self.float_fv_saved_x  = cfg.get("float_fv_saved_x", "")
# ... etc for all new vars ...
self.appear_s_controls = cfg.get("appear_s_controls", True)
self.appear_s_infra    = cfg.get("appear_s_infra", True)
# ... etc ...
```

#### D. Event handlers — floating panels

**Floating mode toggle:**
```python
def toggle_floating_panels_mode(self, checked: bool):
    self.floating_panels_mode = checked
    self._save_current_config()
    if checked:
        return AppState.init_all_float_panels

def flip_floating_panels_mode(self):
    self.floating_panels_mode = not self.floating_panels_mode
    self._save_current_config()
    if self.floating_panels_mode:
        return AppState.init_all_float_panels
```

**`init_all_float_panels`** — fires all three panel initialisers sequentially:
```python
def init_all_float_panels(self):
    return [
        AppState.init_float_file_viewer,
        AppState.init_float_terminal,
        AppState.init_float_object_viewer,
    ]
```

**Per-panel open/close** (repeat pattern ×3, shown for file viewer):
```python
def toggle_float_file_viewer(self, checked: bool):
    self.float_file_viewer_open = checked
    self._save_current_config()
    if checked:
        return AppState.init_float_file_viewer

def flip_float_file_viewer(self):
    self.float_file_viewer_open = not self.float_file_viewer_open
    self._save_current_config()
    if self.float_file_viewer_open:
        return AppState.init_float_file_viewer

def close_float_file_viewer(self):
    """Close panel, save its current position, uncheck Panels menu."""
    self.float_file_viewer_open = False
    self._save_current_config()
    return [
        rx.call_script(
            "document.documentElement.style.getPropertyValue('--fv-x')||''",
            callback=AppState.save_float_fv_x,
        ),
        rx.call_script(
            "document.documentElement.style.getPropertyValue('--fv-y')||''",
            callback=AppState.save_float_fv_y,
        ),
    ]

def save_float_fv_x(self, val: str):
    if val:
        self.float_fv_saved_x = val
        self._save_current_config()

def save_float_fv_y(self, val: str):
    if val:
        self.float_fv_saved_y = val
        self._save_current_config()
```

Repeat `close_float_terminal` / `save_float_term_x/y` and
`close_float_object_viewer` / `save_float_ov_x/y` with CSS vars `--term-x/y` / `--ov-x/y`.

**JS drag initialisers** — one per panel.  Build as Python f-string (safe, no user input).
`saved_x`/`saved_y` injected from Reflex state at handler call time.

```python
def init_float_file_viewer(self):
    sx = self.float_fv_saved_x or ""
    sy = self.float_fv_saved_y or ""
    js = (
        "(function(){"
        "requestAnimationFrame(function(){"
        "  var win=document.getElementById('float-fv-window');"
        "  var hdr=document.getElementById('float-fv-header');"
        "  if(!win||!hdr)return;"
        "  if(!win._positionSet){"
        "    win._positionSet=true;"
        f"    var sx={repr(sx)},sy={repr(sy)};"
        "    if(sx&&sy){"
        "      win.style.left=sx;win.style.top=sy;"
        "      document.documentElement.style.setProperty('--fv-x',sx);"
        "      document.documentElement.style.setProperty('--fv-y',sy);"
        "    }else{"
        "      var cx=window.innerWidth/2,cy=window.innerHeight/2;"
        "      var x=Math.round(cx-300),y=Math.round(cy-220);"   # file viewer offset
        "      win.style.left=x+'px';win.style.top=y+'px';"
        "      win.style.width='600px';win.style.height='440px';"
        "      document.documentElement.style.setProperty('--fv-x',x+'px');"
        "      document.documentElement.style.setProperty('--fv-y',y+'px');"
        "    }"
        "  }"
        "  if(hdr._dragInstalled)return;"
        "  hdr._dragInstalled=true;"
        "  var dragging=false,ox=0,oy=0,sl=0,st=0;"
        "  hdr.addEventListener('pointerdown',function(e){"
        "    if(e.target.closest('button'))return;"
        "    dragging=true;ox=e.clientX;oy=e.clientY;"
        "    sl=parseInt(win.style.left)||win.getBoundingClientRect().left;"
        "    st=parseInt(win.style.top)||win.getBoundingClientRect().top;"
        "    hdr.setPointerCapture(e.pointerId);e.preventDefault();"
        "  });"
        "  hdr.addEventListener('pointermove',function(e){"
        "    if(!dragging)return;"
        "    var nx=sl+e.clientX-ox,ny=st+e.clientY-oy;"
        "    win.style.left=nx+'px';win.style.top=ny+'px';"
        "    document.documentElement.style.setProperty('--fv-x',nx+'px');"
        "    document.documentElement.style.setProperty('--fv-y',ny+'px');"
        "  });"
        "  hdr.addEventListener('pointerup',function(e){"
        "    if(!dragging)return;dragging=false;"
        "    hdr.releasePointerCapture(e.pointerId);"
        "  });"
        "});"
        "})()"
    )
    return rx.call_script(js)
```

Centre offsets (Q4 option b, 30 px stagger):
- File viewer: `cx-300, cy-220`
- Terminal: `cx-270, cy-190`  (30 px down-right)
- Object viewer: `cx-240, cy-160`  (60 px down-right)

Default size for all: `600px × 440px` — user can resize immediately.

Repeat `init_float_terminal` (CSS `--term-x/y`, ids `float-term-window/header`) and
`init_float_object_viewer` (CSS `--ov-x/y`, ids `float-ov-window/header`).

#### E. Event handlers — accordion section toggles

10 flip handlers (one per section):
```python
def flip_appear_s_controls(self): self.appear_s_controls = not self.appear_s_controls; self._save_current_config()
def flip_appear_s_infra(self):    self.appear_s_infra    = not self.appear_s_infra;    self._save_current_config()
def flip_appear_s_wave(self):     self.appear_s_wave     = not self.appear_s_wave;     self._save_current_config()
def flip_appear_s_file(self):     self.appear_s_file     = not self.appear_s_file;     self._save_current_config()
def flip_appear_s_popup(self):    self.appear_s_popup    = not self.appear_s_popup;    self._save_current_config()
def flip_appear_s_terminal(self): self.appear_s_terminal = not self.appear_s_terminal; self._save_current_config()
def flip_appear_s_params(self):   self.appear_s_params   = not self.appear_s_params;   self._save_current_config()
def flip_appear_s_networks(self): self.appear_s_networks = not self.appear_s_networks; self._save_current_config()
def flip_appear_s_layout(self):   self.appear_s_layout   = not self.appear_s_layout;   self._save_current_config()
def flip_appear_s_theme(self):    self.appear_s_theme    = not self.appear_s_theme;    self._save_current_config()
```

#### F. New helper: `_appearance_section()`

```python
def _appearance_section(
    title: str,
    is_open: rx.Var,
    on_toggle,
    *children,
) -> rx.Component:
    """Collapsible titled section for the appearance menu accordion."""
    return rx.vstack(
        rx.hstack(
            rx.text(
                rx.cond(is_open, "▾", "▸"),
                " ",
                title,
                font_size="11px",
                font_weight="600",
                color="var(--gui-text-muted)",
                text_transform="uppercase",
                letter_spacing="0.06em",
            ),
            on_click=on_toggle,
            cursor="pointer",
            padding_x="6px",
            padding_y="6px",
            width="100%",
            _hover={"background": "var(--gui-hover-soft)"},
            border_radius="4px",
        ),
        rx.cond(
            is_open,
            rx.vstack(*children, spacing="0", padding_x="4px", padding_bottom="4px"),
            rx.fragment(),
        ),
        rx.separator(width="100%"),
        spacing="0",
        width="100%",
    )
```

#### G. New component: `float_file_viewer_panel()`

```python
def float_file_viewer_panel() -> rx.Component:
    return rx.cond(
        AppState.floating_panels_mode & AppState.float_file_viewer_open,
        rx.box(
            rx.hstack(
                rx.text("File Viewer", font_size="12px", font_weight="600",
                        color="var(--gui-text-primary)", flex="1"),
                rx.button("✕", on_click=AppState.close_float_file_viewer,
                          variant="ghost", size="1", cursor="pointer",
                          flex_shrink="0", title="Close"),
                align="center", spacing="2",
                padding_x="12px", padding_y="8px",
                cursor="grab",
                id="float-fv-header",
                background="var(--gui-panel-bg)",
                border_bottom="1px solid var(--gui-border)",
                border_radius="8px 8px 0 0",
                user_select="none",
                width="100%",
            ),
            rx.box(
                bottom_left_panel(),
                flex="1", overflow="hidden", min_height="0", width="100%",
            ),
            id="float-fv-window",
            display="flex",
            flex_direction="column",
            position="fixed",
            style={
                "left": "var(--fv-x, 100px)",
                "top": "var(--fv-y, 100px)",
                "width": "600px",
                "min_width": "280px",
                "min_height": "200px",
                "max_height": "95vh",
                "resize": "both",
                "overflow": "hidden",
                "z_index": "9990",
                "border": "1px solid var(--gui-border)",
                "border_radius": "8px",
                "box_shadow": "0 8px 32px rgba(0,0,0,0.28)",
                "background": "var(--gui-content-bg)",
            },
        ),
        rx.box(),
    )
```

Repeat for `float_terminal_panel()` (wraps `bottom_right_panel()`, ids `float-term-*`,
CSS vars `--term-x/y`) and `float_object_viewer_panel()` (wraps `top_right_panel()`,
ids `float-ov-*`, CSS vars `--ov-x/y`).

#### H. New function: `panels_menu()`

```python
def panels_menu() -> rx.Component:
    """Panels dropdown — controls which floating panels are visible."""
    return rx.dropdown_menu.root(
        rx.dropdown_menu.trigger(
            rx.button("Panels ▾", variant="ghost", size="2",
                      title="Show/hide floating panels"),
        ),
        rx.dropdown_menu.content(
            rx.vstack(
                _appearance_menu_item(
                    "File viewer",
                    AppState.float_file_viewer_open,
                    AppState.toggle_float_file_viewer,
                    AppState.flip_float_file_viewer,
                ),
                _appearance_menu_item(
                    "Terminal",
                    AppState.float_terminal_open,
                    AppState.toggle_float_terminal,
                    AppState.flip_float_terminal,
                ),
                _appearance_menu_item(
                    "Object viewer",
                    AppState.float_object_viewer_open,
                    AppState.toggle_float_object_viewer,
                    AppState.flip_float_object_viewer,
                ),
                spacing="0",
                padding="4px",
            ),
            rx.cond(
                ~AppState.floating_panels_mode,
                rx.text(
                    "Enable floating panels in Appearance → Layout",
                    font_size="11px",
                    color="var(--gui-text-dim)",
                    padding_x="8px",
                    padding_y="4px",
                    max_width="200px",
                    white_space="pre-wrap",
                ),
                rx.fragment(),
            ),
            min_width="200px",
        ),
    )
```

#### I. `navbar()` — add `panels_menu()`

Find the `appearance_menu()` call in `navbar()`. Add `panels_menu()` immediately after it.

#### J. `index()` — floating layout branch + floating panel components

Wrap the existing normal/maximized `rx.cond` in a new outer cond:

```python
rx.cond(
    AppState.floating_panels_mode,
    # ── Floating mode layout: infra tree sidebar only ──────────────
    rx.box(
        left_panel(),
        id="left-column",
        overflow_y="auto",
        overflow_x="hidden",
        height="100%",
        border_right="1px solid var(--gui-border)",
        style={
            "min_width": AppState.left_panel_width_style,
            "width": "max-content",
            "height": "calc(100vh - 40px)",   # 40px = navbar height
        },
    ),
    # ── Normal / maximized layout (unchanged) ──────────────────────
    rx.cond(
        AppState.maximized_panel == "",
        <existing normal 4-panel rx.box ...>,
        <existing maximized rx.box ...>,
    ),
),
# Floating panel windows (always in DOM; gate internally via rx.cond)
float_file_viewer_panel(),
float_terminal_panel(),
float_object_viewer_panel(),
```

The three floating panel calls go at the same level as the existing
`hover_popup_window()` call.

#### K. Rewrite `appearance_menu()` using accordion

Replace the entire body of `rx.dropdown_menu.content(...)` (lines ~12970–13540) with
10 `_appearance_section()` calls. The existing items inside each section are unchanged —
just wrapped.

Section groupings:
| Section var | Title | Items |
|---|---|---|
| `appear_s_controls` | Show in controls bar | View selector, Show merged, Depth |
| `appear_s_infra` | Infra tree | Full module name, Wave numbers, Build status + refresh controls |
| `appear_s_wave` | Wave panel | Start/end/duration/age/update + Highlight recent |
| `appear_s_file` | File viewer | Render markdown, Show line numbers |
| `appear_s_popup` | Unit detail popup | Show unit popup on select |
| `appear_s_terminal` | Terminal | Hide auto-run commands, Backend |
| `appear_s_params` | Params panel | Wrap long values |
| `appear_s_networks` | Nested networks | Dependency arrows, Color by wave, Zoom speed |
| `appear_s_layout` | Layout | **Floating panels mode** (new), Drag Width |
| `appear_s_theme` | Theme & App | Theme buttons, Refresh, Open in |

The "Floating panels mode" checkbox is the first item in the Layout section, using
`_appearance_menu_item("Floating panels mode", AppState.floating_panels_mode,
AppState.toggle_floating_panels_mode, AppState.flip_floating_panels_mode)`.

---

## Execution Order

1. Add state vars (section A)
2. Update `_save_current_config` (section B)
3. Update `on_load` (section C)
4. Add event handlers: floating mode + per-panel + position-save callbacks (section D)
5. Add accordion flip handlers (section E)
6. Add `_appearance_section()` helper (section F) — above `appearance_menu()`
7. Add three floating panel components (section G) — above `index()`
8. Add `panels_menu()` (section H) — above or near `help_menu()`
9. Update `navbar()` to call `panels_menu()` (section I)
10. Update `index()` — floating layout branch + add floating panel calls (section J)
11. Rewrite `appearance_menu()` body using accordion (section K)

---

## Verification

- `reflex run` from `infra/de3-gui-pkg/_application/de3-gui/`
- Appearance menu opens; 10 accordion sections visible; click to expand/collapse works
- "Panels ▾" button appears in navbar next to Appearance
- Enable "Floating panels mode" (Appearance → Layout section):
  - Left panel stays fixed, expands if wide node paths are present
  - Three floating panels appear stacked near viewport centre
  - Hint text in Panels menu disappears
- Drag each floating panel — position updates; click another node — panel doesn't jump
- Close a panel with ✕ — Panels menu checkbox unchecks
- Reopen panel via Panels menu — panel appears at last-closed position
- Disable floating mode — normal 4-panel layout restored
- Refresh page with floating mode ON — mode and positions restored from config
