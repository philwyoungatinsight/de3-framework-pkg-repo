"""Repo discovery and scanning for fw-repos-diagram-exporter."""
from __future__ import annotations

import os
import subprocess
import time
from collections import deque
from pathlib import Path

import yaml


def needs_refresh(cfg: dict, sdir: Path) -> bool:
    ar = cfg.get("auto_refresh", {})
    mode = ar.get("mode", "file_age")
    if mode == "never":
        return False
    min_interval = ar.get("min_interval_seconds", 10)
    marker = sdir / "last-refresh"
    last_ts = marker.stat().st_mtime if marker.exists() else 0.0
    age = time.time() - last_ts
    if age < min_interval:
        return False
    if mode == "fixed_time":
        return True
    # file_age: check if any framework_*.yaml in known settings dirs is newer than last-refresh
    from .config import repo_root
    root = repo_root()
    cache_base = Path.home() / cfg.get("repos_cache_dir", "git/fw_repos_diagram_exporter_cache")
    search_roots = [root]
    if cache_base.exists():
        search_roots += [p for p in cache_base.iterdir() if p.is_dir()]
    for sr in search_roots:
        for settings_dir in _find_settings_dirs(sr):
            for f in settings_dir.glob("framework_*.yaml"):
                if f.stat().st_mtime > last_ts:
                    return True
    return False


def _check_accessible(url: str, timeout: int = 10) -> bool:
    """Return True if the git remote answers to ls-remote within timeout seconds."""
    try:
        r = subprocess.run(
            ["git", "ls-remote", "--exit-code", "--quiet", url, "HEAD"],
            capture_output=True, timeout=timeout,
        )
        return r.returncode == 0
    except Exception:
        return False


def _repo_name_from_git(root: Path) -> str:
    """Derive repo name from git remote.origin.url; fall back to directory name."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, check=True,
        )
        url = result.stdout.strip()
        if url:
            return Path(url.rstrip("/").removesuffix(".git")).name
    except Exception:
        pass
    return root.name


def run_scan(cfg: dict, sdir: Path) -> None:
    from .config import repo_root, _fw_cfg_path
    root = repo_root()
    cache_base = Path.home() / cfg.get("repos_cache_dir", "git/fw_repos_diagram_exporter_cache")
    cache_base.mkdir(parents=True, exist_ok=True)
    show_caps = (
        cfg.get("show_capability_deps", False)
        or cfg.get("show_capabilities_in_diagram", False)
    )

    seen_urls: set[str] = set()
    queue: deque[dict] = deque()
    result: dict = {}

    def _norm(url: str) -> str:
        return url.rstrip("/").removesuffix(".git")

    def _enqueue_repos(repo_list: list[dict]) -> None:
        for r in repo_list:
            url = r.get("url")
            if not url:
                continue
            n = _norm(url)
            if n not in seen_urls:
                seen_urls.add(n)
                queue.append(r)

    # Seed from framework_package_repositories.yaml (3-tier lookup)
    repos_yaml = _fw_cfg_path(root, "framework_package_repositories.yaml")
    if repos_yaml.exists():
        raw = yaml.safe_load(repos_yaml.read_text()) or {}
        _enqueue_repos(raw.get("framework_package_repositories", []))

    # Derive current repo name before seeding so it can be used as declaring_repo.
    current_name = _repo_name_from_git(root)

    # Seed source_repos from framework_repo_manager.yaml (3-tier lookup)
    fw_mgr_yaml = _fw_cfg_path(root, "framework_repo_manager.yaml")
    lineage: dict[str, str] = {}           # generated_repo_name → declaring_repo_name
    declared_repos: dict[str, dict] = {}   # generated_repo_name → stub entry
    if fw_mgr_yaml.exists():
        _load_repo_manager(fw_mgr_yaml, lineage, declared_repos, _enqueue_repos,
                           declaring_repo=current_name)
    _scan_dir(root, current_name, None, result, _enqueue_repos, show_caps,
              lineage, declared_repos)
    # Back-fill upstream_url from the declared stub (keeps source="local").
    declared_url = (declared_repos.get(current_name) or {}).get("url")
    if declared_url and current_name in result:
        result[current_name]["url"] = declared_url
    # Back-fill main_package from declared stub if not already read from config/_framework.yaml
    declared_cp = (declared_repos.get(current_name) or {}).get("main_package", "")
    if declared_cp and current_name in result and not result[current_name].get("main_package"):
        result[current_name]["main_package"] = declared_cp

    while queue:
        repo_info = queue.popleft()
        name = repo_info["name"]
        url = repo_info["url"]
        clone_path = cache_base / name
        reachable = _clone_or_pull(url, clone_path)
        _scan_dir(clone_path, name, url, result, _enqueue_repos, show_caps,
                  lineage, declared_repos)
        # Mark inaccessible if clone/pull failed; always set so the viewer can color it.
        if not reachable:
            result.setdefault(name, {})["accessible"] = False

    # Merge declared-only repos not reached by BFS
    for rname, stub in declared_repos.items():
        if rname not in result:
            result[rname] = stub

    # Optional: replace clone-based reachability with an explicit ls-remote probe.
    if cfg.get("check_accessibility", False):
        for entry in result.values():
            url = entry.get("url")
            if url:
                entry["accessible"] = _check_accessible(url)

    _write_state(sdir, result)
    (sdir / "last-refresh").touch()


def _load_repo_manager(
    mgr_yaml: Path,
    lineage: dict,
    declared_repos: dict,
    enqueue_fn,
    declaring_repo: str = "",
) -> None:
    """Parse a framework_repo_manager.yaml and populate lineage + declared_repos.

    declaring_repo is the name of the repo whose directory contains mgr_yaml.
    It becomes created_by for every framework_repos entry, because the repo
    that *declares* a generated repo in its settings is the one that creates it —
    not source_repo, which is just the code template source.
    """
    raw = yaml.safe_load(mgr_yaml.read_text()) or {}
    mgr = raw.get("framework_repo_manager") or {}
    enqueue_fn([
        {"name": r["name"], "url": r["url"]}
        for r in (mgr.get("source_repos") or [])
        if "url" in r
    ])
    pkg_template = mgr.get("framework_package_template")
    for fr in (mgr.get("framework_repos") or []):
        rname = fr["name"]
        src = fr.get("source_repo", "")
        # declaring_repo wins over source_repo: the repo whose config file lists
        # this entry is the one that creates it; source_repo is just the template.
        creator = declaring_repo or src
        # Last-write-wins: later scans (cloned repos) override earlier template scans.
        lineage[rname] = creator
        pkgs = []
        if pkg_template:
            pkgs.append({
                "name": pkg_template["name"],
                "package_type": pkg_template.get("package_type", "external"),
                "exportable": pkg_template.get("exportable", True),
            })
        for p in (fr.get("framework_packages") or []):
            pkgs.append({
                "name": p["name"],
                "package_type": p.get("package_type", ""),
                "exportable": p.get("exportable", False),
            })
        # Derive main_package: prefer is_main_package flag, fall back to sole embedded pkg
        config_pkg = ""
        for p in (fr.get("framework_packages") or []):
            if p.get("is_main_package"):
                config_pkg = p["name"]
                break
        if not config_pkg:
            embedded = [p for p in fr.get("framework_packages", []) if p.get("package_type") == "embedded"]
            if len(embedded) == 1:
                config_pkg = embedded[0]["name"]
        new_labels = list(fr.get("labels") or [])
        # Preserve existing labels if the new declaration carries none (non-empty wins).
        # This prevents template repos (e.g. de3-runner) from wiping labels that a
        # deployment repo already declared for the same repo entry.
        existing_labels = (declared_repos.get(rname) or {}).get("labels", [])
        _remotes = (fr.get("new_repo_config") or {}).get("git-remotes", [])
        upstream = _remotes[0].get("git-source", "") if _remotes else ""
        local_only = bool(fr.get("local_only", False))
        declared_repos[rname] = {
            "url": upstream or None,
            "created_by": creator,
            "source": "declared",
            "local_only": local_only,
            "settings_dirs": [{"path": f"infra/{rname}", "packages": pkgs}],
            "main_package": config_pkg,
            "notes": [str(n) for n in (fr.get("notes") or [])],
            "labels": new_labels if new_labels else existing_labels,
        }
        # Enqueue repos that have a remote URL and are not local_only.
        # local_only repos don't exist on remote yet; cloning them would mark them accessible:false.
        if upstream and not local_only:
            enqueue_fn([{"name": rname, "url": upstream}])


def _find_settings_dirs(path: Path) -> list[Path]:
    """Find all _framework_settings dirs under path, following symlinks, without infinite loops."""
    results = []
    seen_real: set[str] = set()
    for dirpath, dirnames, _ in os.walk(str(path), followlinks=True):
        real = os.path.realpath(dirpath)
        if real in seen_real:
            dirnames.clear()
            continue
        seen_real.add(real)
        if "_framework_settings" in dirnames:
            results.append(Path(dirpath) / "_framework_settings")
            dirnames.remove("_framework_settings")
    return sorted(results)


def _clone_or_pull(url: str, path: Path) -> bool:
    """Clone or pull the repo. Returns True on success, False if unreachable."""
    try:
        if (path / ".git").exists():
            subprocess.run(
                ["git", "-C", str(path), "pull", "--ff-only", "--quiet"],
                check=True,
            )
        else:
            subprocess.run(["git", "clone", "--quiet", url, str(path)], check=True)
        return True
    except Exception:
        return False


def _scan_dir(
    path: Path,
    name: str,
    url,
    result: dict,
    enqueue_fn,
    show_caps: bool,
    lineage: dict,
    declared_repos: dict,
) -> None:
    entry = result.setdefault(name, {
        "url": url,
        "created_by": lineage.get(name),
        "source": "cloned" if url else "local",
        "settings_dirs": [],
    })
    if url:
        entry["url"] = url
        entry["source"] = "cloned"
    if lineage.get(name):
        entry["created_by"] = lineage[name]

    # Back-fill notes, labels, and main_package from declared_repos unconditionally —
    # even if the clone failed and path doesn't exist, the declaring repo's metadata
    # should survive. main_package may be overridden below by config/_framework.yaml.
    decl_stub = declared_repos.get(name) or {}
    decl_notes = decl_stub.get("notes", [])
    if decl_notes and not entry.get("notes"):
        entry["notes"] = decl_notes
    decl_labels = decl_stub.get("labels", [])
    if decl_labels and not entry.get("labels"):
        entry["labels"] = decl_labels
    decl_mp = decl_stub.get("main_package", "")
    if decl_mp and not entry.get("main_package"):
        entry["main_package"] = decl_mp

    if not path.exists():
        return  # clone failed; nothing to scan

    # Read main_package and labels from config/_framework.yaml if present.
    # Labels declared here are authoritative and override any declared-only
    # labels that came from the declaring repo's framework_repo_manager.yaml.
    config_yaml = path / "config" / "_framework.yaml"
    if config_yaml.exists():
        try:
            cfg_raw = yaml.safe_load(config_yaml.read_text()) or {}
            fw_cfg = cfg_raw.get("_framework", {})
            cp = fw_cfg.get("main_package", "")
            if cp:
                entry["main_package"] = cp
            repo_labels = fw_cfg.get("labels", [])
            if repo_labels:
                entry["labels"] = repo_labels
        except Exception:
            pass

    # Read framework_backend from the main package's settings dir
    config_pkg = entry.get("main_package", "")
    if config_pkg:
        fb_path = (path / "infra" / config_pkg
                   / "_config" / "_framework_settings" / "framework_backend.yaml")
        if fb_path.exists():
            try:
                fb_raw = yaml.safe_load(fb_path.read_text()) or {}
                fb = fb_raw.get("framework_backend")
                if fb:
                    entry["framework_backend"] = fb
            except Exception:
                pass

    for sd in _find_settings_dirs(path):
        rel = str(sd.relative_to(path))
        packages = []

        pkgs_yaml = sd / "framework_packages.yaml"
        if pkgs_yaml.exists():
            raw = yaml.safe_load(pkgs_yaml.read_text()) or {}
            for p in (raw.get("framework_packages") or []):
                pkg_entry: dict = {
                    "name": p["name"],
                    "package_type": p.get("package_type", ""),
                    "exportable": p.get("exportable", False),
                }
                if show_caps:
                    pkg_cfg = path / "infra" / p["name"] / "_config" / f"{p['name']}.yaml"
                    if pkg_cfg.exists():
                        pc = yaml.safe_load(pkg_cfg.read_text()) or {}
                        ps = pc.get(p["name"], {})
                        pkg_entry["provides_capability"] = ps.get("_provides_capability", [])
                        pkg_entry["requires_capability"] = ps.get("_requires_capability", [])
                packages.append(pkg_entry)

        # Discover new repos from framework_package_repositories.yaml
        repos_yaml = sd / "framework_package_repositories.yaml"
        if repos_yaml.exists():
            raw = yaml.safe_load(repos_yaml.read_text()) or {}
            enqueue_fn(raw.get("framework_package_repositories") or [])

        # Discover additional source_repos and lineage from framework_repo_manager.yaml
        mgr_yaml = sd / "framework_repo_manager.yaml"
        if mgr_yaml.exists():
            _load_repo_manager(mgr_yaml, lineage, declared_repos, enqueue_fn,
                               declaring_repo=name)

        entry["settings_dirs"].append({"path": rel, "packages": packages})


def _write_state(sdir: Path, repos: dict) -> None:
    from ruamel.yaml import YAML
    state_file = sdir / "known-fw-repos.yaml"
    ry = YAML()
    ry.preserve_quotes = True
    if state_file.exists():
        with open(state_file) as f:
            existing = ry.load(f) or {}
    else:
        existing = {}
    if not isinstance(existing.get("data"), dict):
        existing["data"] = {}
    existing["data"]["repos"] = repos
    with open(state_file, "w") as f:
        ry.dump(existing, f)
