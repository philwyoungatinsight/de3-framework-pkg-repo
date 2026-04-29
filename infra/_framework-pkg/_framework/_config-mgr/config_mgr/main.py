"""config-mgr CLI — pre-process, read, and write framework config."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

from .generator import generate
from .packages import (
    _fw_cfg_path,
    load_framework_packages,
    pkg_yaml_path,
    resolve_config_source,
)
from .writer import set_config_param, set_raw_key


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(result.stdout.strip())


def _config_dir(repo_root: Path) -> Path:
    env_val = os.environ.get("_CONFIG_DIR")
    if env_val:
        return Path(env_val)
    # Fallback: derive from standard layout (used by 'generate' entry point
    # which does not source set_env.sh)
    dynamic_dir = os.environ.get("_DYNAMIC_DIR")
    if dynamic_dir:
        return Path(dynamic_dir) / "config"
    # Last resort: construct from repo root
    return repo_root / "config" / "tmp" / "dynamic" / "config"


def _merge_ancestor_params(config_params: dict, unit_path: str) -> dict:
    """Apply ancestor-merge for a unit path — same algorithm as root.hcl."""
    parts = unit_path.split("/")
    result: dict = {}
    for i in range(1, len(parts) + 1):
        prefix = "/".join(parts[:i])
        entry = config_params.get(prefix)
        if isinstance(entry, dict):
            result.update(entry)
    return result


def cmd_fw_setting(args: argparse.Namespace) -> None:
    repo_root = _repo_root()
    name = args.name
    if not name.endswith(".yaml"):
        name = name + ".yaml"
    path = _fw_cfg_path(repo_root, name)
    if not path.exists():
        sys.exit(f"config-mgr: fw-setting: file not found after 3-tier lookup: {path}")
    print(path)


def cmd_generate(args: argparse.Namespace) -> None:
    repo_root = _repo_root()
    cfg_dir = _config_dir(repo_root)
    generate(repo_root, cfg_dir, output_mode=args.output_mode)


def cmd_get(args: argparse.Namespace) -> None:
    repo_root = _repo_root()
    cfg_dir = _config_dir(repo_root)
    unit_path = args.unit_path.strip("/")
    pkg_name = unit_path.split("/")[0]

    out_yaml = cfg_dir / f"{pkg_name}.yaml"
    if not out_yaml.exists():
        sys.exit(
            f"config-mgr: no config file for '{pkg_name}' at {out_yaml}\n"
            "Run: config-mgr generate"
        )

    data = yaml.safe_load(out_yaml.read_text()) or {}
    pkg_section = data.get(pkg_name, {}) or {}
    config_params = pkg_section.get("config_params", {}) or {}

    merged = _merge_ancestor_params(config_params, unit_path)
    if not merged:
        print(f"(no config_params found for '{unit_path}')")
        return

    print(yaml.dump(merged, default_flow_style=False, allow_unicode=True), end="")


def cmd_set(args: argparse.Namespace) -> None:
    repo_root = _repo_root()
    unit_path = args.unit_path.strip("/")

    # Parse value: try as YAML scalar, fall back to string
    try:
        value = yaml.safe_load(args.value)
    except yaml.YAMLError:
        value = args.value

    set_config_param(
        unit_path=unit_path,
        key=args.key,
        value=value,
        sops=args.sops,
        repo_root=repo_root,
    )

    # Regenerate after write
    cfg_dir = _config_dir(repo_root)
    generate(repo_root, cfg_dir, output_mode="silent")


def cmd_set_raw(args: argparse.Namespace) -> None:
    repo_root = _repo_root()

    try:
        value = yaml.safe_load(args.value)
    except yaml.YAMLError:
        value = args.value

    set_raw_key(
        pkg_name=args.pkg,
        yaml_key_path=args.yaml_key_path,
        value=value,
        sops=args.sops,
        repo_root=repo_root,
    )

    cfg_dir = _config_dir(repo_root)
    generate(repo_root, cfg_dir, output_mode="silent")


def cmd_move(args: argparse.Namespace) -> None:
    """Rename config_params keys (delegates from unit-mgr)."""
    repo_root = _repo_root()
    src = args.src.strip("/")
    dst = args.dst.strip("/")

    src_pkg = src.split("/")[0]
    dst_pkg = dst.split("/")[0]
    packages = load_framework_packages(repo_root)

    src_target = resolve_config_source(src_pkg, packages)
    dst_target = resolve_config_source(dst_pkg, packages)

    src_yaml = pkg_yaml_path(repo_root, src_target)
    dst_yaml = pkg_yaml_path(repo_root, dst_target)

    # Import here to reuse unit-mgr's migrate_config_params
    try:
        sys.path.insert(0, str(repo_root / "infra" / "_framework-pkg" / "_framework" / "_unit-mgr"))
        from unit_mgr.config_yaml import migrate_config_params  # type: ignore
        n = migrate_config_params(
            src_yaml_path=src_yaml,
            dst_yaml_path=dst_yaml,
            src_pkg=src_target,
            dst_pkg=dst_target,
            src_rel=src,
            dst_rel=dst,
            operation="move",
        )
        print(f"config-mgr: moved {n} config_params key(s)")
    except ImportError:
        sys.exit("config-mgr move: unit_mgr not available — ensure unit-mgr is set up")

    cfg_dir = _config_dir(repo_root)
    generate(repo_root, cfg_dir, output_mode="silent")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="config-mgr",
        description=(
            "Pre-process, read, and write framework config.\n\n"
            "Config is sourced from infra/<pkg>/_config/<pkg>.yaml and merged into\n"
            "$_CONFIG_DIR for fast Terragrunt access. Secrets files (.secrets.sops.yaml)\n"
            "are copied encrypted — never decrypted to disk."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run 'config-mgr <command> --help' for per-command usage and examples.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # generate
    g = sub.add_parser(
        "generate",
        help="Pre-process all source config into $_CONFIG_DIR",
        description=(
            "Merge each package's config_params (following config_source chains) and write\n"
            "one <pkg>.yaml per package to $_CONFIG_DIR. Copy encrypted .secrets.sops.yaml\n"
            "files unchanged. Incremental — skips packages whose source files are unchanged.\n\n"
            "Called automatically by set, set-raw, and move. Also invoked by set_env.sh."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  config-mgr generate                        # regenerate stale packages\n"
            "  config-mgr generate --output-mode verbose  # show all packages, including up-to-date ones\n"
            "  config-mgr generate --output-mode silent   # suppress all output\n"
        ),
    )
    g.add_argument(
        "--output-mode",
        choices=["normal", "silent", "verbose"],
        default=None,
        help="Override output_mode from framework_config_mgr.yaml (default: from config)",
    )

    # get
    gt = sub.add_parser(
        "get",
        help="Print merged config_params for a unit path",
        description=(
            "Print the ancestor-merged config_params for UNIT_PATH, using the same algorithm\n"
            "as root.hcl: walks each prefix of UNIT_PATH from shallowest to deepest, overlaying\n"
            "matching config_params entries.\n\n"
            "Reads from $_CONFIG_DIR — run 'config-mgr generate' first if config is stale."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  config-mgr get pwy-home-lab-pkg/_stack/maas/pwy-homelab\n"
            "  config-mgr get pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-01\n"
            "  config-mgr get gcp-pkg/_stack/gcp\n"
        ),
    )
    gt.add_argument(
        "unit_path",
        metavar="UNIT_PATH",
        help="Slash-separated unit path, e.g. proxmox-pkg/_stack/proxmox/pwy-homelab/pve-nodes/pve-1",
    )

    # set
    s = sub.add_parser(
        "set",
        help="Write a config_params key to the correct source file",
        description=(
            "Write KEY=VALUE into config_params[UNIT_PATH] in the package's source YAML.\n"
            "Follows config_source routing: writes to the terminal source package, not the\n"
            "requesting package. Regenerates $_CONFIG_DIR after writing.\n\n"
            "VALUE is parsed as a YAML scalar (numbers, booleans, and null are typed;\n"
            "quote strings that look like scalars, e.g. '\"true\"').\n"
            "Dot-separated KEY writes into a nested dict, e.g. 'token.id'.\n\n"
            "Use --sops to write to the encrypted secrets file instead."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  config-mgr set pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-01 _env prod\n"
            "  config-mgr set pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-01 _skip_on_build true\n"
            "  config-mgr set pwy-home-lab-pkg/_stack/maas/pwy-homelab token.id 'root@pam!mytoken'\n"
            "  config-mgr set pwy-home-lab-pkg/_stack/maas/pwy-homelab api_key 'abc123' --sops\n"
        ),
    )
    s.add_argument(
        "unit_path",
        metavar="UNIT_PATH",
        help="Unit path, e.g. proxmox-pkg/_stack/proxmox/pwy-homelab/pve-nodes/pve-1",
    )
    s.add_argument(
        "key",
        metavar="KEY",
        help="config_params key to set; dot-separated for nested dicts, e.g. 'token.id'",
    )
    s.add_argument("value", metavar="VALUE", help="Value, parsed as a YAML scalar")
    s.add_argument(
        "--sops",
        action="store_true",
        help="Write to <pkg>.secrets.sops.yaml instead of the plain config file",
    )

    # set-raw
    sr = sub.add_parser(
        "set-raw",
        help="Write an arbitrary top-level key in a package's config YAML",
        description=(
            "Write an arbitrary key anywhere in a package's config YAML — not scoped to\n"
            "config_params. Use this for top-level fields like _provides_capability or\n"
            "custom vars sections. Follows config_source routing. Regenerates $_CONFIG_DIR\n"
            "after writing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  config-mgr set-raw pwy-home-lab-pkg _provides_capability 1.2.3\n"
            "  config-mgr set-raw gcp-pkg vars.cluster_name pwy-homelab\n"
            "  config-mgr set-raw pwy-home-lab-pkg some_top_level_secret 'value' --sops\n"
        ),
    )
    sr.add_argument("pkg", metavar="PKG", help="Package name, e.g. proxmox-pkg")
    sr.add_argument(
        "yaml_key_path",
        metavar="KEY_PATH",
        help="Dot-separated path in the YAML, e.g. '_provides_capability' or 'vars.cluster_name'",
    )
    sr.add_argument("value", metavar="VALUE", help="Value, parsed as a YAML scalar")
    sr.add_argument(
        "--sops",
        action="store_true",
        help="Write to <pkg>.secrets.sops.yaml instead of the plain config file",
    )

    # move
    mv = sub.add_parser(
        "move",
        help="Rename config_params keys when a unit path changes",
        description=(
            "Move all config_params entries under SRC to DST in the package config YAML.\n"
            "Use when renaming a unit directory to keep config in sync with the new path.\n"
            "Delegates to unit-mgr's migrate_config_params. Regenerates $_CONFIG_DIR after writing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  config-mgr move \\\n"
            "    pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/old-name \\\n"
            "    pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/new-name\n"
        ),
    )
    mv.add_argument("src", metavar="SRC", help="Source unit path (current name)")
    mv.add_argument("dst", metavar="DST", help="Destination unit path (new name)")

    # fw-setting
    fw = sub.add_parser(
        "fw-setting",
        help="Print the resolved path to a framework settings file",
        description=(
            "Resolve a framework settings filename through the 3-tier lookup\n"
            "(per-dev config/ → consumer _framework_settings/ → framework default)\n"
            "and print the absolute path of the winning file.\n\n"
            "Useful in bash scripts to avoid duplicating the lookup logic:\n"
            "  YAML=$(config-mgr fw-setting framework_ramdisk)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  config-mgr fw-setting framework_ramdisk\n"
            "  config-mgr fw-setting framework_ramdisk.yaml\n"
            "  config-mgr fw-setting framework_clean_all\n"
        ),
    )
    fw.add_argument(
        "name",
        metavar="FILENAME",
        help="Framework settings filename, e.g. framework_ramdisk or framework_ramdisk.yaml",
    )

    return p


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    effective = argv if argv is not None else sys.argv[1:]
    if not effective:
        parser.print_help(sys.stderr)
        sys.exit(2)
    args = parser.parse_args(argv)

    dispatch = {
        "generate": cmd_generate,
        "get": cmd_get,
        "set": cmd_set,
        "set-raw": cmd_set_raw,
        "move": cmd_move,
        "fw-setting": cmd_fw_setting,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
