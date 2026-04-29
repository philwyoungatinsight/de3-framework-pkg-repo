#!/usr/bin/env python3
"""Clear anomalous port_override entries from the UniFi Pro Max 16-Port.

Two classes of anomaly are detected:

  STALE   — portconf_id points to a portconf that no longer exists in UniFi
             (left behind after a Terraform destroy of a port profile).
             Fix: remove the portconf_id from the override; if the override
             has no name either, remove the entry entirely.

  GHOST   — port_override entry with neither a name nor a portconf_id.
             These are no-op entries created when Terraform writes an empty
             port config (name='', port_profile='').  They carry no useful
             information and cause the UniFi UI to show the port as "custom".
             Fix: remove the entry from the port_overrides array entirely.

In dry-run mode (default) the script only reports findings.
Pass --fix to apply the cleaned port_overrides via PUT.

Usage:
    clear-promax-anomalies.py <config.json> [--fix]

Config JSON (written by the Ansible playbook):
{
  "unifi_url":  "https://192.168.2.1",
  "promax_mac": "9c:05:d6:e4:f9:a1"
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
                    if name.strip().upper() == "TOKEN":
                        csrf_token["value"] = value.strip()
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
    return request


# ── Anomaly detection and fix ─────────────────────────────────────────────────

def run(config, request, fix):
    promax_mac = config["promax_mac"].lower()

    print("Fetching devices from UniFi ...", flush=True)
    devices_resp = request("GET", "/proxy/network/api/s/default/stat/device")

    print("Fetching port profiles (portconfs) from UniFi ...", flush=True)
    portconfs_resp = request("GET", "/proxy/network/api/s/default/rest/portconf")

    valid_portconf_ids = {p["_id"] for p in portconfs_resp["data"]}
    portconf_names = {p["_id"]: p.get("name", p["_id"]) for p in portconfs_resp["data"]}

    print(f"\nValid portconf IDs ({len(valid_portconf_ids)}):")
    for pid, pname in sorted(portconf_names.items()):
        print(f"  {pid}  →  {pname!r}")

    # Find the Pro Max device
    promax = next(
        (d for d in devices_resp["data"] if d.get("mac", "").lower() == promax_mac),
        None,
    )
    if promax is None:
        print(f"\nERROR: Pro Max (MAC {promax_mac}) not found in UniFi.", file=sys.stderr)
        sys.exit(1)

    device_id = promax["_id"]
    print(f"\nFound Pro Max: {promax.get('name', promax_mac)}  (id={device_id})")

    current_overrides = promax.get("port_overrides", [])
    print(f"\nCurrent port_overrides ({len(current_overrides)} entries):")

    stale_ports = []
    ghost_ports = []
    clean_overrides = []

    for override in current_overrides:
        port_idx = override.get("port_idx", "?")
        portconf_id = override.get("portconf_id", "")
        port_name = override.get("name", "")

        is_stale = bool(portconf_id) and portconf_id not in valid_portconf_ids
        is_ghost = not portconf_id and not port_name.strip()

        if is_stale:
            tag = "  [STALE portconf_id]"
            stale_ports.append(port_idx)
        elif is_ghost:
            tag = "  [GHOST — empty entry]"
            ghost_ports.append(port_idx)
        else:
            tag = ""

        profile_info = (
            f"STALE id={portconf_id!r}"
            if is_stale
            else (f"OK → profile={portconf_names[portconf_id]!r}" if portconf_id else "no profile (default)")
        )
        print(
            f"  port {port_idx:>3}  name={port_name!r:20}  "
            f"portconf_id={portconf_id or '(none)':<30}  {profile_info}{tag}"
        )

        if is_ghost:
            pass  # omit from clean_overrides entirely
        elif is_stale:
            # Strip the bad portconf_id; keep the entry only if name is set
            cleaned = {k: v for k, v in override.items() if k != "portconf_id"}
            if cleaned.get("name", "").strip():
                clean_overrides.append(cleaned)
            # else both name and portconf_id are gone — treat as ghost, omit
        else:
            clean_overrides.append(override)

    total_anomalies = len(stale_ports) + len(ghost_ports)
    print(f"\nStale portconf_id entries : {len(stale_ports)} (ports: {sorted(stale_ports) or 'none'})")
    print(f"Ghost (empty) entries     : {len(ghost_ports)} (ports: {sorted(ghost_ports) or 'none'})")
    print(f"Total anomalies           : {total_anomalies}")

    if total_anomalies == 0:
        print("\nNo anomalies found — nothing to do.")
        return

    print(f"\nCleaned port_overrides will have {len(clean_overrides)} entries "
          f"(removed {len(current_overrides) - len(clean_overrides)}).")

    if not fix:
        print("\nDry-run mode — pass --fix to apply changes.")
        return

    print(f"\nApplying fix via PUT /device/{device_id} ...")
    payload = {"port_overrides": clean_overrides}
    result = request("PUT", f"/proxy/network/api/s/default/rest/device/{device_id}", data=payload)
    if result.get("meta", {}).get("rc") == "ok":
        print(f"Fixed {total_anomalies} anomaly/anomalies successfully.")
    else:
        print(f"Unexpected response: {json.dumps(result)}", file=sys.stderr)
        sys.exit(1)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: clear-promax-anomalies.py <config.json> [--fix]", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        config = json.load(f)

    fix = "--fix" in sys.argv

    username = os.environ.get("UNIFI_USERNAME")
    password = os.environ.get("UNIFI_PASSWORD")
    if not username or not password:
        print("ERROR: UNIFI_USERNAME and UNIFI_PASSWORD must be set", file=sys.stderr)
        sys.exit(1)

    unifi_url = config["unifi_url"].rstrip("/")
    try:
        client = make_client(unifi_url, username, password)
        run(config, client, fix=fix)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
