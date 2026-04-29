#!/usr/bin/env python3
"""
Fix ms01-01 MaaS interface link state.

Problem: maas_instance.this deploy fails with:
  "This interface <mac> has a reserved ip 10.0.12.237 but it does not
   have a link to that subnet"

Cause: force-release via direct DB UPDATE left stale IP reservations
on the NIC without proper interface-to-subnet link records.

Fix:
  1. Read all physical interfaces for the machine
  2. Unlink all existing links on each physical interface
  3. Re-link each interface to its subnet with mode=AUTO
     (same logic as commission-and-wait.sh _configure_interfaces)

Usage: python3 fix_interface_link.py <system_id>
  Run as root or via sudo on the MaaS server.
"""

import json
import subprocess
import sys


def maas(*args, check=True):
    """Run a maas CLI command and return parsed JSON output."""
    cmd = ["maas", "admin"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: {' '.join(cmd)} failed:", file=sys.stderr)
        print(f"  stdout: {result.stdout.strip()}", file=sys.stderr)
        print(f"  stderr: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    if result.stdout.strip():
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return result.stdout.strip()
    return None


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <system_id>", file=sys.stderr)
        sys.exit(1)

    system_id = sys.argv[1]
    print(f"Fixing interface links for {system_id}...")

    # Fetch data
    ifaces = maas("interfaces", "read", system_id)
    subnets = maas("subnets", "read")

    # Build VLAN-to-subnet and DHCP-subnet lookups
    vlan_to_subnet = {}
    dhcp_subnet_ids = []
    for s in subnets:
        vlan = s.get("vlan") or {}
        vid = vlan.get("id")
        if vid is not None and vid not in vlan_to_subnet:
            vlan_to_subnet[vid] = str(s["id"])
        if vlan.get("dhcp_on"):
            dhcp_subnet_ids.append(str(s["id"]))

    errors = 0
    for iface in ifaces:
        if iface.get("type") != "physical":
            continue

        iface_id = iface["id"]
        iface_name = iface["name"]
        links = iface.get("links") or []
        vlan_id = (iface.get("vlan") or {}).get("id")

        # Determine target subnet
        if links:
            sub_id = str((links[0].get("subnet") or {}).get("id", ""))
        elif vlan_id is not None:
            sub_id = vlan_to_subnet.get(vlan_id, "")
        elif dhcp_subnet_ids:
            sub_id = dhcp_subnet_ids[0]
        else:
            sub_id = ""

        print(f"\nInterface: {iface_name} (id={iface_id})")
        if links:
            print(f"  Existing links: {[l['id'] for l in links]}")
        else:
            print("  No existing links")
        print(f"  Target subnet_id: {sub_id or '(none found)'}")

        # Step 1: Unlink all existing links
        for link in links:
            link_id = link["id"]
            print(f"  Unlinking link id={link_id}...")
            result = subprocess.run(
                ["maas", "admin", "interface", "unlink-subnet",
                 system_id, str(iface_id), f"id={link_id}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"    OK")
            else:
                print(f"    WARNING: unlink failed (may already be gone): {result.stderr.strip()}")

        # Step 2: Re-link with AUTO mode
        if sub_id:
            print(f"  Linking to subnet={sub_id} mode=AUTO...")
            result = subprocess.run(
                ["maas", "admin", "interface", "link-subnet",
                 system_id, str(iface_id),
                 "mode=AUTO", f"subnet={sub_id}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"    OK")
            else:
                print(f"    ERROR: link-subnet failed: {result.stderr.strip()}")
                errors += 1
        else:
            print(f"  SKIP: no subnet found for {iface_name}")

    # Verify final state
    print("\n=== Final interface state ===")
    ifaces_after = maas("interfaces", "read", system_id)
    for iface in ifaces_after:
        if iface.get("type") != "physical":
            continue
        links = iface.get("links") or []
        if links:
            for l in links:
                sub = l.get("subnet") or {}
                print(f"  {iface['name']} (id={iface['id']}): "
                      f"link={l['id']} mode={l.get('mode')} subnet={sub.get('cidr')}")
        else:
            print(f"  {iface['name']} (id={iface['id']}): NO LINKS")

    if errors:
        print(f"\nFINISHED with {errors} error(s)", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\nDone — interfaces fixed successfully.")


if __name__ == "__main__":
    main()
