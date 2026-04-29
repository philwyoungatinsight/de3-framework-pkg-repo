"""Render known-fw-repos.yaml into output files."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml


def render_all(cfg: dict, sdir: Path, formats: list[str]) -> list[Path]:
    state_file = sdir / "known-fw-repos.yaml"
    if not state_file.exists():
        print("fw-repos-diagram-exporter: no state found — run --refresh first", file=sys.stderr)
        return []
    raw = yaml.safe_load(state_file.read_text()) or {}
    data = raw.get("data", {})
    repos = data.get("repos", {})
    show_cap_deps = cfg.get("show_capability_deps", False)
    show_cap_labels = cfg.get("show_capabilities_in_diagram", False)
    show_lineage = cfg.get("show_repo_lineage", True)

    ext_map = {"yaml": "yaml", "json": "json", "text": "txt", "dot": "dot"}
    written: list[Path] = []
    for fmt in formats:
        if fmt not in ext_map:
            print(f"fw-repos-diagram-exporter: unknown format '{fmt}', skipping", file=sys.stderr)
            continue
        out_path = sdir / f"output.{ext_map[fmt]}"
        content = _render(fmt, repos, show_cap_deps, show_cap_labels, show_lineage)
        out_path.write_text(content)
        written.append(out_path)
    return written


def _render(
    fmt: str,
    repos: dict,
    show_cap_deps: bool,
    show_cap_labels: bool,
    show_lineage: bool,
) -> str:
    if fmt == "yaml":
        return yaml.dump({"repos": repos}, default_flow_style=False, allow_unicode=True)
    if fmt == "json":
        return json.dumps({"repos": repos}, indent=2)
    if fmt == "text":
        return _render_text(repos, show_cap_deps, show_cap_labels, show_lineage)
    if fmt == "dot":
        return _render_dot(repos, show_cap_deps, show_cap_labels, show_lineage)
    return ""


def _render_text(
    repos: dict,
    show_cap_deps: bool,
    show_cap_labels: bool,
    show_lineage: bool,
) -> str:
    lines: list[str] = []
    for repo_name, repo_data in repos.items():
        url = repo_data.get("url") or "local"
        created_by = repo_data.get("created_by")
        src_tag = repo_data.get("source", "cloned")
        lineage_str = f"  [created by: {created_by}]" if (show_lineage and created_by) else ""
        declared_str = "  [declared only]" if src_tag == "declared" else ""
        lines.append(f"{repo_name}  ({url}){lineage_str}{declared_str}")
        for lbl in repo_data.get("labels", []):
            lbl_value = lbl.get("value")
            if lbl_value is not None:
                lines.append(f"  [{lbl['name']}] {lbl_value}")
        sdirs = repo_data.get("settings_dirs", [])
        for i, sd in enumerate(sdirs):
            is_last_sd = i == len(sdirs) - 1
            sd_prefix = "└── " if is_last_sd else "├── "
            pkg_prefix = "    " if is_last_sd else "│   "
            lines.append(f"{sd_prefix}{sd['path']}")
            pkgs = sd.get("packages", [])
            for j, pkg in enumerate(pkgs):
                is_last_pkg = j == len(pkgs) - 1
                p_prefix = pkg_prefix + ("└── " if is_last_pkg else "├── ")
                flags = []
                if pkg.get("package_type"):
                    flags.append(pkg["package_type"])
                if pkg.get("exportable"):
                    flags.append("exportable")
                flag_str = f"  [{', '.join(flags)}]" if flags else ""
                cap_parts: list[str] = []
                if show_cap_labels:
                    for c in pkg.get("provides_capability", []):
                        cap_parts.append(f"provides: {c}")
                if show_cap_deps:
                    for c in pkg.get("requires_capability", []):
                        cap_parts.append(f"requires: {c}")
                cap_str = "  " + ", ".join(cap_parts) if cap_parts else ""
                lines.append(f"{p_prefix}{pkg['name']}{flag_str}{cap_str}")
        lines.append("")
    return "\n".join(lines)


def _to_browse_url(git_url: str) -> str | None:
    """Normalize a git remote URL to a browseable HTTPS URL. Returns None if unrecognized."""
    if not git_url:
        return None
    url = git_url.strip().rstrip("/").removesuffix(".git")
    if url.startswith("git@"):
        # git@github.com:org/repo → https://github.com/org/repo
        url = "https://" + url[len("git@"):].replace(":", "/", 1)
    if url.startswith(("https://", "http://")):
        return url
    return None


def _fw_repo_mgr_url(browse_url: str, config_package: str) -> str:
    """Construct the GitHub blob URL to framework_repo_manager.yaml in config_package."""
    return (
        f"{browse_url}/blob/HEAD"
        f"/infra/{config_package}/_config/_framework_settings/framework_repo_manager.yaml"
    )


def _render_dot(
    repos: dict,
    show_cap_deps: bool,
    show_cap_labels: bool,
    show_lineage: bool,
) -> str:
    lines = [
        "digraph fw_repos {",
        "  compound=true;",
        "  rankdir=LR;",
        "  node [fontname=Helvetica];",
        "",
    ]
    cap_providers: dict[str, str] = {}   # capability-name → package-node-id
    repo_anchor: dict[str, str] = {}     # repo-name → first node-id in that cluster
    repo_cluster: dict[str, int] = {}    # repo-name → cluster index

    cluster_idx = 0
    for repo_name, repo_data in repos.items():
        is_declared = repo_data.get("source") == "declared"
        fill = "lightgrey" if is_declared else "lightyellow"
        lines.append(f"  subgraph cluster_{cluster_idx} {{")

        url = repo_data.get("url") or ""
        browse_url = _to_browse_url(url)
        created_by = repo_data.get("created_by") or ""
        subtitle = f"\\n{url}" if url else ""
        if show_lineage and created_by:
            subtitle += f"\\ncreated by: {created_by}"
        if is_declared:
            subtitle += "\\n[declared only]"
        for lbl in repo_data.get("labels", []):
            if lbl.get("name") == "_purpose" and lbl.get("value"):
                subtitle += f"\\n{lbl['value']}"
                break
        lines.append(f'    label="{repo_name}{subtitle}";')
        lines.append(f"    style=filled; fillcolor={fill};")
        main_package = repo_data.get("main_package")
        if browse_url and main_package:
            fw_url = _fw_repo_mgr_url(browse_url, main_package)
            lines.append(f'    URL="{fw_url}";')
            lines.append('    target="_blank";')

        first_node: str | None = None
        for sd in repo_data.get("settings_dirs", []):
            sd_id = _dot_id(f"{repo_name}_{sd['path']}")
            if first_node is None:
                first_node = sd_id
            lines.append(
                f'    {sd_id} [label="{sd["path"]}", shape=box, '
                f"style=filled, fillcolor=lightblue];"
            )
            for pkg in sd.get("packages", []):
                pkg_id = _dot_id(f"{repo_name}_{pkg['name']}")
                cap_label = ""
                if show_cap_labels:
                    provides = pkg.get("provides_capability", [])
                    if provides:
                        cap_label = "\\n" + "\\n".join(str(c) for c in provides)
                url_attr = f', URL="{browse_url}", target="_blank"' if browse_url else ""
                lines.append(
                    f'    {pkg_id} [label="{pkg["name"]}{cap_label}", shape=ellipse{url_attr}];'
                )
                lines.append(f"    {sd_id} -> {pkg_id};")
                if show_cap_labels or show_cap_deps:
                    for cap in pkg.get("provides_capability", []):
                        cap_name = (
                            str(cap).split(":")[0].strip()
                            if ":" in str(cap)
                            else str(cap)
                        )
                        cap_providers[cap_name] = pkg_id

        if first_node:
            repo_anchor[repo_name] = first_node
        repo_cluster[repo_name] = cluster_idx
        cluster_idx += 1
        lines.append("  }")
        lines.append("")

    if show_lineage:
        lines.append("  // repo lineage edges (source repo -> generated repo)")
        for repo_name, repo_data in repos.items():
            created_by = repo_data.get("created_by")
            if (
                created_by
                and created_by in repo_anchor
                and repo_name in repo_anchor
            ):
                src_node = repo_anchor[created_by]
                dst_node = repo_anchor[repo_name]
                src_ci = repo_cluster[created_by]
                dst_ci = repo_cluster[repo_name]
                lines.append(
                    f"  {src_node} -> {dst_node} "
                    f"[ltail=cluster_{src_ci}, lhead=cluster_{dst_ci}, "
                    f'style=bold, color=darkgreen, label="creates"];'
                )
        lines.append("")

    if show_cap_deps:
        lines.append("  // capability dependency edges")
        for repo_name, repo_data in repos.items():
            for sd in repo_data.get("settings_dirs", []):
                for pkg in sd.get("packages", []):
                    pkg_id = _dot_id(f"{repo_name}_{pkg['name']}")
                    for req in pkg.get("requires_capability", []):
                        req_name = (
                            str(req).split(":")[0].strip()
                            if ":" in str(req)
                            else str(req)
                        )
                        if req_name in cap_providers:
                            lines.append(
                                f"  {pkg_id} -> {cap_providers[req_name]} "
                                f'[style=dashed, label="requires"];'
                            )
        lines.append("")

    lines.append("}")
    return "\n".join(lines)


def _dot_id(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", s)
