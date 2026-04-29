"""fw-repos-diagram-exporter CLI."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .config import load_config, state_dir
from .renderer import render_all
from .scanner import needs_refresh, run_scan


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fw-repos-diagram-exporter",
        description="Discover framework repos and export as diagram files (yaml, json, text, dot).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  fw-repos-diagram-exporter --refresh\n"
            "  fw-repos-diagram-exporter --list\n"
            "  fw-repos-diagram-exporter --list --format text,dot\n"
            "  fw-repos-diagram-exporter --refresh --list\n"
            "  fw-repos-diagram-exporter --list --no-auto-refresh\n"
        ),
    )
    p.add_argument(
        "-r", "--refresh",
        action="store_true",
        help="Force immediate scan; update known-fw-repos.yaml and last-refresh",
    )
    p.add_argument(
        "-l", "--list",
        action="store_true",
        help="Render all configured output formats to state dir",
    )
    p.add_argument(
        "-f", "--format",
        metavar="FORMATS",
        help="Comma-separated formats for this run (yaml,json,text,dot); overrides config",
    )
    p.add_argument(
        "--auto-refresh",
        dest="auto_refresh",
        action="store_true",
        default=None,
        help="Auto-refresh before render if stale (overrides auto_refresh_on_render in config)",
    )
    p.add_argument(
        "--no-auto-refresh",
        dest="auto_refresh",
        action="store_false",
        help="Skip auto-refresh check before render",
    )
    p.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Copy first rendered output to FILE; use - for stdout",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    p = _build_parser()
    effective = argv if argv is not None else sys.argv[1:]
    if not effective:
        p.print_help(sys.stderr)
        sys.exit(2)
    args = p.parse_args(effective)

    cfg = load_config()
    sdir = state_dir()
    sdir.mkdir(parents=True, exist_ok=True)

    formats = (
        [f.strip() for f in args.format.split(",")]
        if args.format
        else cfg.get("output_formats", ["yaml", "text"])
    )

    will_render = args.list or bool(args.format)
    on_render = cfg.get("auto_refresh", {}).get("auto_refresh_on_render", True)
    effective_auto = args.auto_refresh if args.auto_refresh is not None else on_render

    do_refresh = args.refresh or (will_render and effective_auto and needs_refresh(cfg, sdir))
    if do_refresh:
        run_scan(cfg, sdir)

    if will_render:
        paths = render_all(cfg, sdir, formats)
        if args.output:
            if args.output == "-" and paths:
                sys.stdout.write(Path(paths[0]).read_text())
            elif paths:
                shutil.copy(str(paths[0]), args.output)
        else:
            for out in paths:
                print(out)


if __name__ == "__main__":
    main()
