# Plan: Right-Click Context Menu on Framework Repos Canvas

## Objective

Replace the current left-click git URL opening on Mermaid class-diagram nodes in the
Framework Repos view with a right-click context menu. The menu exposes two actions per
repo node: open the repo's git URL in a browser tab, and open its
`framework_package_repositories.yaml` config file. Removing the left-click navigation
prevents accidental navigation while dragging the canvas.

## Context

All changes are in one file:
`infra/de3-gui-pkg/_application/de3-gui/assets/fw_repos_mermaid_viewer.html`
(actual path: `/home/pyoung/git/de3-ext-packages/de3-runner/main/infra/de3-gui-pkg/_application/de3-gui/assets/fw_repos_mermaid_viewer.html`)

The viewer is a standalone HTML file loaded in an `<iframe>` inside the Reflex GUI.
It fetches repo data from `/api/fw-repos-graph` (returns `{repos: {<name>: {url, main_package, ...}}}`)
and builds a Mermaid `classDiagram` definition that is rendered into an SVG.

**Current left-click behavior (lines 219–236):**
Mermaid `link` directives are appended to the diagram definition. Mermaid wraps each
class-title text in an `<a>` tag. Left-clicking navigates to:
- `<browse_url>/blob/main/infra/<main_package>/_config/_framework_settings/framework_repo_manager.yaml`
  if `main_package` is set, or
- `<browse_url>` (repo root) otherwise.

This fires even after a short drag because `<a>` responds to click, not mousedown.
The pan handler only prevents text selection (via `e.preventDefault()` on mousedown) —
it does not suppress click events on anchor tags.

**Data already available per repo:**
- `url` — git remote URL (may be `null` for local-only repos)
- `main_package` — config package name (e.g. `pwy-home-lab-pkg`), may be absent

**URL construction helpers needed in JS:**
- Convert `git@host:org/repo` or `https://host/org/repo.git` to a browser URL:
  `url.replace(/^git@([^:]+):(.+)$/, 'https://$1/$2').replace(/\.git$/, '')`
- GitHub browse path: `<base>/blob/main/<path>`
- GitLab browse path: `<base>/-/blob/main/<path>`
  (detect GitLab by checking `url.indexOf('gitlab') !== -1`)

**Finding SVG class-node groups after render:**
Mermaid 11 class diagrams assign each node a `<g id="classid-<name>-<N>">` element.
After `mermaid.render()`, use `textEl.closest('[id^="classid-"]')` on each `<text>`
whose `textContent.trim()` matches a repo's `safeName(name)`. This locates the
correct node group to attach the `contextmenu` handler to, covering the full node
box rather than just the text.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/de3-gui-pkg/_application/de3-gui/assets/fw_repos_mermaid_viewer.html` — modify

**1. Replace the `link`-directive CSS (lines 25–27) with context-menu CSS.**

Remove:
```css
/* Highlight clickable class nodes (Mermaid link directive wraps title in <a>) */
#diagram svg a text { fill: #93c5fd; font-weight: bold; }
#diagram svg a:hover text { fill: #dbeafe; }
```
Replace with:
```css
#ctx-menu .ctx-item:hover { background: #334155; }
#ctx-menu .ctx-item.disabled { color: #475569; cursor: default; }
#ctx-menu .ctx-item.disabled:hover { background: transparent; }
```

**2. Add the context-menu `<div>` to `<body>` (after the `#diagram-wrap` div, before `<script>`).**

```html
<div id="ctx-menu" style="display:none; position:fixed; z-index:1000;
  background:#1e293b; border:1px solid #334155; border-radius:6px;
  padding:4px 0; min-width:240px;
  box-shadow:0 4px 16px rgba(0,0,0,0.6);
  font-size:13px; font-family:system-ui,-apple-system,sans-serif;">
  <div id="ctx-git"    class="ctx-item" style="padding:8px 16px; cursor:pointer; color:#e2e8f0; white-space:nowrap;">Open Git URL</div>
  <div id="ctx-fw-pkg" class="ctx-item" style="padding:8px 16px; cursor:pointer; color:#e2e8f0; white-space:nowrap;">Open framework_package_repositories.yaml</div>
</div>
```

**3. Remove the `link` directive block (lines 219–236) from `buildMermaid()`.**

Delete the entire block:
```javascript
// link directives make class names clickable
// If main_package is known, link to its framework_repo_manager.yaml in the repo;
// otherwise fall back to the repo root URL.
names.forEach(function(name) {
  var r = repos[name];
  if (!r.url) return;
  ...
});
```

**4. Add context-menu logic in `<script>`, after the `_zoom / _applyZoom` block and before `_renderDiagram`.**

```javascript
// ── Context menu ─────────────────────────────────────────────────────────────
var _ctxTarget = null;

function _toBrowseUrl(url) {
  if (!url) return '';
  return url.replace(/^git@([^:]+):(.+)$/, 'https://$1/$2').replace(/\.git$/, '');
}

function showContextMenu(x, y, name, data) {
  _ctxTarget = {name: name, data: data};
  var hasUrl   = !!data.url;
  var hasFwPkg = hasUrl && !!data.main_package;

  var gitItem = document.getElementById('ctx-git');
  var fwItem  = document.getElementById('ctx-fw-pkg');
  gitItem.classList.toggle('disabled', !hasUrl);
  fwItem.classList.toggle('disabled', !hasFwPkg);

  var menu = document.getElementById('ctx-menu');
  menu.style.display = 'block';
  // Clamp to viewport so the menu never clips off-screen
  var mw = menu.offsetWidth, mh = menu.offsetHeight;
  menu.style.left = Math.min(x, window.innerWidth  - mw - 8) + 'px';
  menu.style.top  = Math.min(y, window.innerHeight - mh - 8) + 'px';
}

function hideContextMenu() {
  document.getElementById('ctx-menu').style.display = 'none';
  _ctxTarget = null;
}

document.getElementById('ctx-git').addEventListener('click', function() {
  if (!_ctxTarget || !_ctxTarget.data.url) return;
  window.open(_toBrowseUrl(_ctxTarget.data.url), '_blank');
  hideContextMenu();
});

document.getElementById('ctx-fw-pkg').addEventListener('click', function() {
  if (!_ctxTarget || !_ctxTarget.data.url || !_ctxTarget.data.main_package) return;
  var base = _toBrowseUrl(_ctxTarget.data.url);
  var pkg  = _ctxTarget.data.main_package;
  var path = 'infra/' + pkg + '/_config/_framework_settings/framework_package_repositories.yaml';
  var url  = base.indexOf('gitlab') !== -1
    ? base + '/-/blob/main/' + path
    : base + '/blob/main/' + path;
  window.open(url, '_blank');
  hideContextMenu();
});

// Dismiss on click outside the menu or on Escape
document.addEventListener('click', function(e) {
  if (!e.target.closest('#ctx-menu')) hideContextMenu();
});
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') hideContextMenu();
});

function attachContextMenuHandlers(repos) {
  var svgEl = document.querySelector('#diagram svg');
  if (!svgEl) return;

  // Build safeName → {name, data} lookup
  var nameMap = {};
  Object.keys(repos).forEach(function(name) {
    nameMap[safeName(name)] = {name: name, data: repos[name]};
  });

  // Each class node title is a <text> whose trimmed content equals safeName(repoName).
  // Walk up to the [id^="classid-"] ancestor (the node's root <g>) to cover the full
  // box with the handler, not just the text element.
  svgEl.querySelectorAll('text').forEach(function(textEl) {
    var txt  = (textEl.textContent || '').trim();
    var repo = nameMap[txt];
    if (!repo) return;

    var nodeG = textEl.closest('[id^="classid-"]') || textEl.parentElement;
    nodeG.addEventListener('contextmenu', function(e) {
      e.preventDefault();
      e.stopPropagation();
      showContextMenu(e.clientX, e.clientY, repo.name, repo.data);
    });
  });
}
```

**5. Call `attachContextMenuHandlers` inside `_renderDiagram()` after `_initZoom()`.**

Change:
```javascript
  document.getElementById('diagram').innerHTML = result.svg;
  _initZoom();
```
To:
```javascript
  document.getElementById('diagram').innerHTML = result.svg;
  _initZoom();
  attachContextMenuHandlers(_repos);
```

## Execution Order

1. Edit `fw_repos_mermaid_viewer.html`:
   a. Replace `link`-directive CSS (lines 25–27) with context-menu CSS
   b. Add `#ctx-menu` HTML div after `#diagram-wrap`
   c. Remove `link` directive forEach block (lines 219–236) from `buildMermaid()`
   d. Add context-menu JS block before `_renderDiagram`
   e. Add `attachContextMenuHandlers(_repos)` call inside `_renderDiagram()`
2. Commit from the `de3-ext-packages` repo

## Verification

1. Open the GUI Framework Repos view
2. Right-click a repo node → context menu appears with two items
3. "Open Git URL" opens the repo's browse URL in a new tab (disabled and greyed-out for local-only repos with no URL)
4. "Open framework_package_repositories.yaml" opens the correct file path in a new tab (disabled when no `main_package`)
5. Left-click + drag no longer triggers navigation
6. Clicking anywhere outside the menu dismisses it; Escape also dismisses it
