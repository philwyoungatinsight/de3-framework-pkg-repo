#!/usr/bin/env python3
"""
Config linter — invoked by set_env.sh at source time.

Reads framework.validate_config from config/framework.yaml to decide whether
to run and where to write the flag file, then validates config YAML file
conventions.  Output is printed to stdout and, in every_n_minutes mode, also
written to the flag file so its mtime tracks the last run.

# RULES
#
# RULE 1 — One top-level key
#   Each file must contain exactly one top-level key.
#   SOPS-encrypted files append a 'sops:' metadata key; it is excluded from
#   the count so that secrets files are held to the same one-key standard.
#
# RULE 2 — Key matches filename stem
#   The single top-level key must equal the filename stem:
#     foo.yaml              → expected key 'foo'
#     foo.sops.yaml         → expected key 'foo'
#     foo_secrets.sops.yaml → expected key 'foo_secrets'
#   Strip '.sops.yaml' before '.yaml' to get the stem.
#
# RULE 3 — Unique stems across the entire search scope
#   All config file stems must be unique so that files can be relocated
#   without breaking lookup code (e.g. _find_component_config searches the
#   whole repo for a key name and returns the first match).
#
# RULE 4 — SOPS files must be decryptable
#   Every *.sops.yaml file is test-decrypted with `sops --decrypt --output
#   /dev/null`.  A failure means the active key (age/GPG/KMS) cannot open the
#   file — usually a missing key or stale encryption recipient.
#
# RULE 5 — Package capability requirements must be satisfied
#   Every package that declares _requires_capability must have each requirement
#   satisfied either by another package's _provides_capability (with a matching
#   version) or by framework.external_capabilities (which lists capabilities
#   fulfilled outside this repo, with their declared versions).
#   Version constraints use >=, >, <=, <, = operators or * (any version).
#
# RULE 6 — config_source chain validation
#   For each package in framework_packages.yaml that declares config_source:
#   - The named package must exist in framework_packages.yaml.
#   - The full chain (following config_source links) must be cycle-free.
#   Detected as: visit each package in a DFS; if any is visited twice, error.
#
# Search scope
#   - infra/*/_config/*.yaml   (all packages including _framework-pkg framework config)
"""

import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("validate-config: pyyaml not found — run: pip install pyyaml")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def git_root() -> Path:
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(r.stdout.strip())


def stem(path: Path) -> str:
    """Return the config stem: strip .sops.yaml or .yaml from the filename."""
    name = path.name
    if name.endswith(".sops.yaml"):
        return name[: -len(".sops.yaml")]
    if name.endswith(".yaml"):
        return name[: -len(".yaml")]
    return name


def collect_files(root: Path) -> list[Path]:
    return sorted(root.glob("infra/*/_config/*.yaml"))


def top_level_keys(path: Path) -> list[str]:
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ValueError(f"YAML parse error: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"top level is not a mapping (got {type(data).__name__})")
    return [k for k in data.keys() if k != "sops"]


from capability_utils import check_capability_requirements
from framework_config import find_framework_config_dirs, load_framework_config


def _load_fw(root: Path) -> dict:
    try:
        return load_framework_config(find_framework_config_dirs(root))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# RULE 5 — capability validation
# ---------------------------------------------------------------------------

def check_capabilities(root: Path) -> list[str]:
    """RULE 5 — validate package capability requirements. Returns list of error strings."""
    try:
        fw = _load_fw(root)
    except Exception:
        return []  # can't read — other rules will surface the parse error

    packages: dict[str, dict] = {}
    for pkg_dir in sorted((root / "infra").iterdir()):
        if not pkg_dir.is_dir():
            continue
        pkg_name = pkg_dir.name
        cfg_file = pkg_dir / "_config" / f"{pkg_name}.yaml"
        if not cfg_file.exists():
            continue
        try:
            raw = yaml.safe_load(cfg_file.read_text())
            pkg_cfg = (raw or {}).get(pkg_name, {}) or {}
            packages[pkg_name] = {k: v for k, v in pkg_cfg.items() if k.startswith('_')}
        except Exception:
            continue  # parse errors caught by earlier rules

    return [
        f"  FAIL [capability]: {e}"
        for e in check_capability_requirements(packages, fw.get("external_capabilities", []))
    ]


# ---------------------------------------------------------------------------
# RULE 6 — config_source chain validation
# ---------------------------------------------------------------------------

def check_config_source_chains(root: Path) -> list[str]:
    """RULE 6 — validate config_source declarations. Returns list of error strings."""
    import os as _os
    pkg_dir = _os.environ.get("_FRAMEWORK_PKG_DIR") or str(root / "infra" / "_framework-pkg")
    fw_pkgs_path = Path(pkg_dir) / "_config" / "framework_packages.yaml"
    if not fw_pkgs_path.exists():
        return []

    try:
        raw = yaml.safe_load(fw_pkgs_path.read_text()) or {}
        packages = raw.get("framework_packages", [])
    except Exception as e:
        return [f"  FAIL [framework_packages.yaml]: could not load: {e}"]

    pkg_names = {p["name"] for p in packages}
    pkg_map = {p["name"]: p for p in packages}
    errors: list[str] = []

    for pkg in packages:
        pkg_name = pkg["name"]
        cs = pkg.get("config_source")
        if not cs:
            continue
        # Check referenced package exists
        if cs not in pkg_names:
            errors.append(
                f"  FAIL [config_source]: '{pkg_name}' declares "
                f"config_source: '{cs}' which does not exist in framework_packages.yaml"
            )
            continue
        # Follow chain with cycle detection
        visited: list[str] = []
        current = pkg_name
        while True:
            if current in visited:
                errors.append(
                    f"  FAIL [config_source]: cycle detected: "
                    f"{' -> '.join(visited + [current])}"
                )
                break
            visited.append(current)
            entry = pkg_map.get(current, {})
            nxt = entry.get("config_source")
            if not nxt:
                break
            if nxt not in pkg_names:
                errors.append(
                    f"  FAIL [config_source]: '{current}' points to "
                    f"'{nxt}' which does not exist in framework_packages.yaml"
                )
                break
            current = nxt

    return errors


# ---------------------------------------------------------------------------
# Rate-limiting: read framework.yaml to decide whether to run
# ---------------------------------------------------------------------------

def check_should_run(root: Path) -> tuple[bool, Path | None]:
    """Return (should_run, flag_path).  flag_path is None when no flag file is used."""
    try:
        fw = _load_fw(root)
    except Exception:
        return True, None   # can't read config — run anyway to surface errors

    vc   = fw.get("validate_config", {})
    mode = vc.get("mode", "disabled")

    if mode == "always":
        return True, None
    if mode == "every_n_minutes":
        interval = int(vc.get("interval_minutes", 60))
        flag     = Path(os.environ.get("_CONFIG_TMP_DIR", str(root / "config" / "tmp"))) / "validate-config-last-run"
        if not flag.exists():
            return True, flag
        return (time.time() - flag.stat().st_mtime) / 60 >= interval, flag
    return False, None   # disabled or unknown mode


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    root               = git_root()
    should_run, flag   = check_should_run(root)
    if not should_run:
        return 0

    try:
        fw = _load_fw(root)
        show_individual = fw.get("validate_config", {}).get("show_individual_files_checked", True)
    except Exception:
        show_individual = True

    files       = collect_files(root)
    sops_files  = [f for f in files if f.name.endswith(".sops.yaml")]
    plain_files = [f for f in files if not f.name.endswith(".sops.yaml")]
    errors: list[str] = []
    lines:  list[str] = []

    def emit(line: str = "") -> None:
        print(line)
        lines.append(line)

    if show_individual:
        emit("validate-config: check files")
    else:
        header = f"validate-config: check files ({len(plain_files)} config, {len(sops_files)} sops)"
        print(header, end=" ", flush=True)
        lines.append(header)

    # RULE 3 — collect stems for uniqueness check
    stem_to_files: dict[str, list[Path]] = defaultdict(list)
    for f in files:
        stem_to_files[stem(f)].append(f)

    for f in files:
        rel      = f.relative_to(root)
        expected = stem(f)
        if show_individual:
            emit(f"  {rel}")
        else:
            print(".", end="", flush=True)

        try:
            keys = top_level_keys(f)
        except ValueError as e:
            errors.append(f"  FAIL [{rel}]: {e}")
            continue

        # RULE 1 — exactly one key
        if len(keys) != 1:
            errors.append(f"  FAIL [{rel}]: expected 1 top-level key, got {len(keys)}: {keys}")
            continue

        # RULE 2 — key matches stem
        actual = keys[0]
        if actual != expected:
            errors.append(
                f"  FAIL [{rel}]: top-level key '{actual}' does not match expected '{expected}'"
            )

    if not show_individual:
        print(flush=True)

    # RULE 3 — unique stems
    for s, paths in sorted(stem_to_files.items()):
        if len(paths) > 1:
            rels = [str(p.relative_to(root)) for p in paths]
            errors.append(
                f"  FAIL [stem '{s}']: duplicate across {len(paths)} files:\n"
                + "\n".join(f"    {r}" for r in rels)
            )

    # RULE 4 — SOPS files must be decryptable
    if sops_files:
        if show_individual:
            emit(f"\nvalidate-config: check SOPS decryption ({len(sops_files)} file(s))")
        else:
            sops_header = f"\nvalidate-config: check SOPS decryption ({len(sops_files)} file(s))"
            print(sops_header, end=" ", flush=True)
            lines.append(sops_header)
        for f in sops_files:
            rel = f.relative_to(root)
            if show_individual:
                emit(f"  {rel}")
            else:
                print(".", end="", flush=True)
            result = subprocess.run(
                ["sops", "--decrypt", "--output", "/dev/null", str(f)],
                capture_output=True,
            )
            if result.returncode != 0:
                errors.append(
                    f"  FAIL [{rel}]: sops decrypt failed — "
                    + result.stderr.decode(errors="replace").strip().splitlines()[0]
                )
        if not show_individual:
            print(flush=True)

    # RULE 5 — capability requirements
    cap_errors = check_capabilities(root)
    if cap_errors:
        emit("\nvalidate-config: check capabilities")
        errors.extend(cap_errors)

    # RULE 6 — config_source chain validation
    cs_errors = check_config_source_chains(root)
    if cs_errors:
        emit("\nvalidate-config: check config_source chains")
        errors.extend(cs_errors)

    checked = len(files)
    if errors:
        emit(f"\nvalidate-config: {checked} files checked, {len(errors)} violation(s):\n")
        for e in errors:
            emit(e)
        emit("\nvalidate-config: WARNING — violations found. Fix before running terragrunt.")
    else:
        emit(f"validate-config: {checked} files checked — all OK")

    # Write flag file: mtime records last run; content holds last output for review.
    if flag is not None:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("\n".join(lines) + "\n")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
