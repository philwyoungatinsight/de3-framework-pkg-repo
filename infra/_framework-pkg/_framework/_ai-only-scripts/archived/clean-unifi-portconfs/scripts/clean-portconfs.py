#!/usr/bin/env python3
"""Detect and delete duplicate and orphaned UniFi portconfs (port profiles).

When Terraform creates and destroys port profiles across deployment cycles,
UniFi may retain orphaned portconf entries with the same display name as a
currently-managed profile.  This script finds those duplicates and removes
the ones that are not referenced by any switch port_override.

Two cleanup modes (both respect --fix / dry-run):
  --duplicates  (always active)
      Within each group sharing a display name:
        - Keep in-use entries and the most-recently-created unused entry.
        - Delete the rest.
  --also-orphans
      After duplicate cleanup, also delete any unused portconf whose name
      does not appear in the set of YAML-managed profile names.  The
      system default ("DEFAULT-HOME-ALLOW-ALL") is always preserved.

Strategy:
  1. Fetch all portconfs.
  2. Group by display name.
  3. Fetch all devices; collect every portconf_id in port_overrides.
  4. Handle duplicate groups (see above).
  5. If --also-orphans: flag unused portconfs with unmanaged names.
  6. Dry-run (default) or --fix to apply.

Usage:
    clean-portconfs.py <config.json> [--fix] [--also-orphans]

Config JSON (written by the Ansible playbook):
{
  "unifi_url":              "https://192.168.2.1",
  "managed_profile_names":  ["Hypervisor Trunk", "PXE and Management", ...]
}

Required environment variables:
    UNIFI_USERNAME
    UNIFI_PASSWORD
"""

import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from collections import defaultdict


# ── UniFi API helpers ──────────────────────────────────────────────────────────

def make_client(unifi_url, username, password):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    cookie_jar = {}
    csrf_token = {"value": None}

    def request(method, path, data=None):
        url = f"{unifi_url}{path}"
        headers = {"Content-Type": "application/json"}
        if cookie_jar:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookie_jar.items())
        # UDM requires X-Csrf-Token for any mutating request (POST/PUT/DELETE)
        if csrf_token["value"] and method.upper() in ("POST", "PUT", "DELETE", "PATCH"):
            headers["X-Csrf-Token"] = csrf_token["value"]
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=ctx) as resp:
                for hdr in resp.headers.get_all("Set-Cookie") or []:
                    name, _, rest = hdr.partition("=")
                    value = rest.split(";")[0]
                    cookie_jar[name.strip()] = value.strip()
                    # UDM exposes the CSRF token as the "TOKEN" cookie value
                    if name.strip().upper() == "TOKEN":
                        csrf_token["value"] = value.strip()
                # Also capture from X-Csrf-Token response header if present
                csrf_hdr = resp.headers.get("X-Csrf-Token")
                if csrf_hdr:
                    csrf_token["value"] = csrf_hdr
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            print(f"HTTP {e.code} from {method} {path}: {body_text}", file=sys.stderr)
            raise

    print(f"Authenticating to {unifi_url} ...", flush=True)
    request("POST", "/api/auth/login", {"username": username, "password": password})
    if csrf_token["value"]:
        print(f"CSRF token captured.", flush=True)
    else:
        print("WARNING: no CSRF token found — DELETE may fail with 403.", flush=True)
    return request


# ── Main logic ─────────────────────────────────────────────────────────────────

def delete_portconfs(to_delete, request, fix, label):
    """Print the to_delete list and optionally DELETE each one."""
    print(f"\n{label}: {len(to_delete)}")
    for pid, name in to_delete:
        print(f"  {pid}  ({name!r})")

    if not to_delete:
        return

    if not fix:
        print("\nDry-run mode — pass --fix to apply deletions.")
        return

    errors = 0
    for pid, name in to_delete:
        print(f"\nDeleting {pid} ({name!r}) ...", flush=True)
        try:
            request("DELETE", f"/proxy/network/api/s/default/rest/portconf/{pid}")
            print("  Deleted OK.")
        except Exception as e:
            print(f"  ERROR deleting {pid}: {e}", file=sys.stderr)
            errors += 1

    if errors:
        print(f"\n{errors} deletion(s) failed.", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\nAll {len(to_delete)} portconf(s) deleted successfully.")


def run(config, request, fix, also_orphans):
    # Names currently declared in the YAML config — never delete these.
    managed_names = {n.lower() for n in config.get("managed_profile_names", [])}
    # The built-in UniFi default profile — always preserve.
    SYSTEM_PREFIX = "default-home"

    print("Fetching portconfs ...", flush=True)
    portconfs_resp = request("GET", "/proxy/network/api/s/default/rest/portconf")
    all_portconfs = portconfs_resp["data"]

    print("Fetching devices (to find portconf references) ...", flush=True)
    devices_resp = request("GET", "/proxy/network/api/s/default/stat/device")
    all_devices = devices_resp["data"]

    # Collect every portconf_id currently referenced by a switch port_override
    referenced_ids = set()
    for dev in all_devices:
        for override in dev.get("port_overrides", []):
            pid = override.get("portconf_id")
            if pid:
                referenced_ids.add(pid)

    print(f"\nAll portconfs ({len(all_portconfs)}):")
    by_name = defaultdict(list)
    for p in all_portconfs:
        pid = p["_id"]
        name = p.get("name", "(unnamed)")
        in_use = pid in referenced_ids
        managed = name.lower() in managed_names
        system = name.lower().startswith(SYSTEM_PREFIX)
        tags = "[IN USE]" if in_use else "[unused]"
        if managed:
            tags += " [managed]"
        if system:
            tags += " [system]"
        print(f"  {pid}  {name!r:30}  {tags}")
        by_name[name].append(p)

    print(f"\nReferenced portconf IDs ({len(referenced_ids)}): {sorted(referenced_ids)}")

    # ── Phase 1: duplicates ────────────────────────────────────────────────────
    duplicate_groups = {name: entries for name, entries in by_name.items() if len(entries) > 1}
    dup_to_delete = []

    if not duplicate_groups:
        print("\nNo duplicate portconf names found.")
    else:
        print(f"\nDuplicate groups ({len(duplicate_groups)}):")
        for name, entries in sorted(duplicate_groups.items()):
            ids = [e["_id"] for e in entries]
            used = [pid for pid in ids if pid in referenced_ids]
            unused = [pid for pid in ids if pid not in referenced_ids]

            print(f"\n  Name: {name!r}")
            for e in entries:
                pid = e["_id"]
                tag = "IN USE" if pid in referenced_ids else "unused"
                print(f"    {pid}  [{tag}]")

            if used:
                for pid in unused:
                    print(f"    → DELETE {pid} (unused duplicate of in-use entry)")
                    dup_to_delete.append((pid, name))
            else:
                keep = max(ids)
                for pid in ids:
                    if pid != keep:
                        print(f"    → DELETE {pid} (duplicate, none in use — keeping {keep})")
                        dup_to_delete.append((pid, name))
                    else:
                        print(f"    → KEEP   {pid} (most recently created)")

    delete_portconfs(dup_to_delete, request, fix, "Duplicate portconfs to delete")

    # ── Phase 2: orphans (unmanaged, unused, non-system singles) ──────────────
    if not also_orphans:
        return

    # Re-fetch after potential deletions so the orphan check is accurate.
    if fix and dup_to_delete:
        print("\nRe-fetching portconfs after duplicate cleanup ...", flush=True)
        portconfs_resp = request("GET", "/proxy/network/api/s/default/rest/portconf")
        all_portconfs = portconfs_resp["data"]

    orphan_to_delete = []
    print("\nChecking for orphaned portconfs (unused, unmanaged, non-system) ...")
    for p in all_portconfs:
        pid = p["_id"]
        name = p.get("name", "(unnamed)")
        in_use = pid in referenced_ids
        is_system = name.lower().startswith(SYSTEM_PREFIX)
        is_managed = name.lower() in managed_names

        if in_use:
            continue
        if is_system:
            print(f"  SKIP  {pid}  {name!r}  (system profile)")
            continue
        if is_managed:
            # Managed but unused — a valid terraform-declared profile; keep it.
            print(f"  KEEP  {pid}  {name!r}  (managed by YAML config, unused but valid)")
            continue

        print(f"  ORPHAN {pid}  {name!r}  → DELETE (unused, not in YAML config)")
        orphan_to_delete.append((pid, name))

    delete_portconfs(orphan_to_delete, request, fix, "Orphaned portconfs to delete")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: clean-portconfs.py <config.json> [--fix]", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        config = json.load(f)

    fix = "--fix" in sys.argv
    also_orphans = "--also-orphans" in sys.argv

    username = os.environ.get("UNIFI_USERNAME")
    password = os.environ.get("UNIFI_PASSWORD")
    if not username or not password:
        print("ERROR: UNIFI_USERNAME and UNIFI_PASSWORD must be set", file=sys.stderr)
        sys.exit(1)

    unifi_url = config["unifi_url"].rstrip("/")
    try:
        client = make_client(unifi_url, username, password)
        run(config, client, fix=fix, also_orphans=also_orphans)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
