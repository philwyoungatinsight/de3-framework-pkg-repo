# Plan: Support Initializing External Repos (GitHub / GitLab)

## Objective

Extend `fw-repo-mgr` to optionally create and initialize remote repos on GitHub and/or
GitLab hosting platforms after building the local git repo. Config-driven via a new
`remote_repos` list on each `framework_repos` entry. If any remote already exists, add
a warning to `$_DYNAMIC_DIR/fw-repo-mgr/warnings.md` (instead of failing) and display
that report at the end of every run.

## Context

### Codebase findings

- **Main script**: `/home/pyoung/git/de3-ext-packages/de3-runner/main/infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr` — 559-line bash script with inline Python3 for all config parsing. All Python runs inline via here-docs or `-c` strings; this is the established pattern to follow.
- **Framework-level config**: `/home/pyoung/git/de3-ext-packages/de3-runner/main/infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml` — template/example config with commented-out blocks.
- **Deployment config**: `/home/pyoung/git/pwy-home-lab-pkg/infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml` — 11 real repo entries, no `remote_repos` yet.
- **`_DYNAMIC_DIR`** is already exported by `set_env.sh` (sourced at script top). The shim at line 435 also sets it to `$_SHIM_ROOT/config/tmp/dynamic`.
- **`gh` CLI** is installed, authenticated (philwyoungatinsight, token scopes: `repo`). Use it for GitHub operations.
- **GitLab CLI** (`glab`) is NOT installed. Must use REST API directly. Token via `GITLAB_TOKEN` env var.
- **`requests` library** is available in Python3 — use it for GitLab HTTP calls.
- No existing GitHub/GitLab API usage patterns in the codebase — establishing new ones here.
- **`_build_repo` step layout**: steps 1–5 (init/update, prune, scaffold, pkg-mgr, commit), step 6 (push to `upstream_url`). New step 5.5 (`_init_remote_repos`) goes between commit and push.

### Naming invariant

The framework repo's `name` field (e.g. `proxmox-pkg-repo`) IS the repo name on the remote
hosting platform. URLs in `remote_repos` always end with that same name. The tool validates
this and fails loudly if the basename differs.

### Dynamic dir and warnings file

- Dir: `$_DYNAMIC_DIR/fw-repo-mgr/`
- File: `$_DYNAMIC_DIR/fw-repo-mgr/warnings.md`
- Lifecycle: cleared at the start of each `fw-repo-mgr build` invocation, appended to
  during repo processing, shown to stdout at the end (success or error via EXIT trap).

## Open Questions

None — ready to proceed.

## Files to Create / Modify

---

### `de3-ext-packages/de3-runner/main/infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr` — modify

**Full path**: `/home/pyoung/git/de3-ext-packages/de3-runner/main/infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr`

Four changes:

#### Change 1 — Add warnings-file helpers (insert after `_find_source_clone` function, before `# Config readers` comment)

```bash
# ---------------------------------------------------------------------------
# Warnings report helpers
# ---------------------------------------------------------------------------
_warnings_file() {
  echo "$_DYNAMIC_DIR/fw-repo-mgr/warnings.md"
}

_init_warnings_file() {
  local wf; wf=$(_warnings_file)
  mkdir -p "$(dirname "$wf")"
  printf "# fw-repo-mgr warnings\n_Generated: %s_\n" "$(date '+%Y-%m-%d %H:%M:%S')" > "$wf"
}

_show_warnings_report() {
  local wf; wf=$(_warnings_file)
  [[ ! -f "$wf" ]] && return 0
  # Count warning lines (lines starting with "- ⚠️")
  local count; count=$(grep -c '^- ⚠️' "$wf" 2>/dev/null || true)
  [[ "$count" -eq 0 ]] && return 0
  echo ""
  echo "╔══════════════════════════════════════╗"
  echo "║      fw-repo-mgr warnings ($count)        ║"
  echo "╚══════════════════════════════════════╝"
  cat "$wf"
  echo ""
  echo "Report saved: $wf"
}
```

#### Change 2 — Add `_init_remote_repos` function (insert before `# Build a single target repo` comment)

```bash
# ---------------------------------------------------------------------------
# Check / create remote repos listed in remote_repos for a framework_repo entry.
# For each URL:
#   - GitHub (github.com): uses 'gh' CLI (must be authenticated)
#   - GitLab (gitlab.*):   uses REST API with GITLAB_TOKEN env var
# If a repo already exists: appends a warning (does NOT fail).
# If a repo cannot be created: exits non-zero (fails the build).
# Repo name is validated against the framework repo name; mismatches fail loudly.
# ---------------------------------------------------------------------------
_init_remote_repos() {   # _init_remote_repos <repo_name>
  local repo_name="$1"
  local wf; wf=$(_warnings_file)

  python3 - "$repo_name" "$FW_MGR_CFG" "$wf" <<'PYEOF'
import sys, json, os, subprocess, pathlib
import urllib.parse

repo_name, cfg_path, warnings_file = sys.argv[1], sys.argv[2], sys.argv[3]

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not available", file=sys.stderr); sys.exit(1)
try:
    import requests as _req
except ImportError:
    _req = None

d = yaml.safe_load(pathlib.Path(cfg_path).read_text()) or {}
repos = d.get('framework_repo_manager', {}).get('framework_repos', [])
target = next((r for r in repos if r.get('name') == repo_name), None)
if not target:
    sys.exit(0)

remote_repos = target.get('remote_repos', [])
if not remote_repos:
    sys.exit(0)

warnings = []

def _append_warnings(lines):
    if not lines:
        return
    wf = pathlib.Path(warnings_file)
    wf.parent.mkdir(parents=True, exist_ok=True)
    with wf.open('a') as f:
        f.write(f"\n## {repo_name}\n")
        for w in lines:
            f.write(f"- ⚠️  {w}\n")

for entry in remote_repos:
    url = entry.get('url', '').rstrip('/')
    visibility = entry.get('visibility', 'private')
    if not url:
        continue

    # Normalise: strip trailing .git
    if url.endswith('.git'):
        url = url[:-4]

    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    path = parsed.path.lstrip('/')
    parts = path.split('/')
    if len(parts) != 2:
        print(f"ERROR: remote_repos URL must have exactly <owner>/<repo> path, got: {url}",
              file=sys.stderr)
        sys.exit(1)
    owner, remote_name = parts[0], parts[1]

    # Validate name matches framework repo name
    if remote_name != repo_name:
        print(f"ERROR: remote repo name '{remote_name}' in URL '{url}' does not match "
              f"framework repo name '{repo_name}'. All remote repos must use the same name.",
              file=sys.stderr)
        sys.exit(1)

    if 'github.com' in host:
        # ---- GitHub: use gh CLI ----
        slug = f"{owner}/{remote_name}"
        check = subprocess.run(
            ['gh', 'repo', 'view', slug, '--json', 'name'],
            capture_output=True, text=True,
        )
        if check.returncode == 0:
            warnings.append(f"GitHub repo already exists (skipped creation): {url}")
            print(f"  [skip] GitHub repo exists: {url}")
        else:
            print(f"  Creating GitHub repo: {url} (visibility={visibility}) ...")
            create = subprocess.run(
                ['gh', 'repo', 'create', slug, f'--{visibility}', '--no-clone'],
                capture_output=True, text=True,
            )
            if create.returncode != 0:
                print(f"ERROR: failed to create GitHub repo {url}:\n{create.stderr}",
                      file=sys.stderr)
                sys.exit(1)
            print(f"  Created GitHub repo: {url}")

    elif 'gitlab' in host:
        # ---- GitLab: use REST API ----
        token = os.environ.get('GITLAB_TOKEN', '')
        if not token:
            print(f"ERROR: GITLAB_TOKEN env var is required to create GitLab repo {url}",
                  file=sys.stderr)
            sys.exit(1)

        if _req is None:
            print("ERROR: 'requests' Python library is required for GitLab API calls",
                  file=sys.stderr)
            sys.exit(1)

        scheme = parsed.scheme or 'https'
        api_base = f"{scheme}://{host}/api/v4"
        headers = {'PRIVATE-TOKEN': token, 'Content-Type': 'application/json'}

        # Check if repo exists
        encoded_path = urllib.parse.quote(f"{owner}/{remote_name}", safe='')
        resp = _req.get(f"{api_base}/projects/{encoded_path}", headers=headers, timeout=30)
        if resp.status_code == 200:
            warnings.append(f"GitLab repo already exists (skipped creation): {url}")
            print(f"  [skip] GitLab repo exists: {url}")
            continue
        elif resp.status_code != 404:
            print(f"ERROR: GitLab API error checking {url}: HTTP {resp.status_code} — {resp.text}",
                  file=sys.stderr)
            sys.exit(1)

        # Resolve namespace_id
        ns_resp = _req.get(f"{api_base}/namespaces",
                           params={'search': owner}, headers=headers, timeout=30)
        if ns_resp.status_code != 200:
            print(f"ERROR: could not list GitLab namespaces for '{owner}': HTTP {ns_resp.status_code}",
                  file=sys.stderr)
            sys.exit(1)
        namespaces = ns_resp.json()
        ns = next((n for n in namespaces if n.get('path') == owner), None)
        if ns is None:
            print(f"ERROR: GitLab namespace '{owner}' not found (searched {host})",
                  file=sys.stderr)
            sys.exit(1)

        # Create project
        print(f"  Creating GitLab repo: {url} (visibility={visibility}) ...")
        create_resp = _req.post(
            f"{api_base}/projects",
            json={
                'name': remote_name,
                'path': remote_name,
                'namespace_id': ns['id'],
                'visibility': visibility,
            },
            headers=headers,
            timeout=30,
        )
        if create_resp.status_code not in (200, 201):
            print(f"ERROR: failed to create GitLab repo {url}: "
                  f"HTTP {create_resp.status_code} — {create_resp.text}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"  Created GitLab repo: {url}")

    else:
        print(f"ERROR: unsupported hosting provider in remote_repos URL: {url}",
              file=sys.stderr)
        sys.exit(1)

_append_warnings(warnings)
PYEOF
}
```

#### Change 3 — Call `_init_remote_repos` in `_build_repo` (between step 5 and step 6)

Find the existing comment `# Step 6: push if upstream_url set` (around line 453) and insert before it:

```bash
  # Step 5.5: create remote repos on hosting platforms (if remote_repos configured)
  _init_remote_repos "$repo_name"
```

#### Change 4 — Init warnings file + trap + show at end in the build CLI dispatch

Replace the `build)` case in the CLI dispatch section:

```bash
  build)
    _init_warnings_file
    trap '_show_warnings_report' EXIT
    if [[ -n "$REPO_NAME" ]]; then
      _build_repo "$REPO_NAME" "$FORCE_PUSH"
    else
      _list_repos \
        | python3 -c "import json,sys; [print(r['name']) for r in json.load(sys.stdin)]" \
        | while IFS= read -r name; do _build_repo "$name" "$FORCE_PUSH"; done
    fi
    ;;
```

Note: `_show_warnings_report` is called via `trap EXIT` so it fires on both normal exit and error.
The trap is set AFTER `_init_warnings_file` so a fresh file always exists when the trap fires.

---

### `de3-ext-packages/de3-runner/main/infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml` — modify

**Full path**: `/home/pyoung/git/de3-ext-packages/de3-runner/main/infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml`

Add `remote_repos` documentation to the `proxmox-pkg-repo` example entry (currently shown
as the first entry in `framework_repos`). Add after `upstream_branch: main`:

```yaml
      # Optional: create these remote repos on hosting platforms if they don't exist.
      # If a repo already exists, a warning is shown at the end of the run but the
      # build continues. Supported providers: github.com (uses gh CLI),
      # gitlab.* (uses GITLAB_TOKEN env var). visibility: private|public (default: private).
      # The repo name (basename of each URL) must match this entry's 'name' field.
      #remote_repos:
      #  - url: https://github.com/<your-org>/proxmox-pkg-repo
      #    visibility: private
      #  - url: https://gitlab.com/<your-group>/proxmox-pkg-repo
      #    visibility: private
```

---

### `pwy-home-lab-pkg/infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml` — modify

**Full path**: `/home/pyoung/git/pwy-home-lab-pkg/infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml`

Add a `remote_repos` block to the `proxmox-pkg-repo` entry (the only entry with an
`upstream_url` that is a real repo on GitHub). This serves as the live example.
Add after `upstream_branch: main`:

```yaml
      remote_repos:
        - url: https://github.com/philwyoungatinsight/proxmox-pkg-repo
          visibility: private
```

This also acts as a live smoke test: running `fw-repo-mgr build proxmox-pkg-repo` will
check that the GitHub repo exists (it does) and emit a warning, exercising the full path.

---

## Execution Order

1. **Modify `fw-repo-mgr`** (the bash script):
   - Insert `_warnings_file`, `_init_warnings_file`, `_show_warnings_report` helpers
   - Insert `_init_remote_repos` function
   - Add step 5.5 call in `_build_repo`
   - Update `build)` dispatch to init warnings + trap

2. **Modify framework-level `framework_repo_manager.yaml`** — add commented `remote_repos` docs

3. **Modify deployment `framework_repo_manager.yaml`** — add live `remote_repos` on `proxmox-pkg-repo`

4. **Run `fw-repo-mgr build proxmox-pkg-repo`** to smoke-test:
   - Should detect existing GitHub repo → emit warning
   - Should display warnings report at end
   - Check `config/tmp/dynamic/fw-repo-mgr/warnings.md` contains the warning

5. **Update version history** for `_framework-pkg` (bump minor version — new feature)

6. **Write ai-log entry** and commit both repos (`de3-runner` and `pwy-home-lab-pkg`)

## Verification

```bash
# Smoke test — should show warning about existing repo, not error
cd /home/pyoung/git/pwy-home-lab-pkg
fw-repo-mgr build proxmox-pkg-repo

# Check warnings file
cat config/tmp/dynamic/fw-repo-mgr/warnings.md

# Confirm no error exit (should be 0)
echo "exit code: $?"

# Confirm non-existent repo would be created (integration test — skip if no test org)
# gh repo delete test-org/test-repo && fw-repo-mgr build test-repo
```

Expected `warnings.md` content after smoke test:
```
# fw-repo-mgr warnings
_Generated: 2026-04-25 ..._

## proxmox-pkg-repo
- ⚠️  GitHub repo already exists (skipped creation): https://github.com/philwyoungatinsight/proxmox-pkg-repo
```
