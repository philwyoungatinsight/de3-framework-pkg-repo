#!/usr/bin/env python3
"""Destroy UniFi resources managed by unifi-pkg.

Reads unifi-pkg.yaml to identify which VLANs and port profiles were created by
this codebase, then deletes them from the controller in the correct order:

  1. Clear managed portconf_id refs from device port overrides
     (unblocks port profile deletion — controller rejects DELETE when a device
     port still references the profile)
  2. Clear managed excluded_networkconf_ids refs from device port overrides
     (unblocks network deletion — controller rejects DELETE when a port still
     excludes the network)
  3. Delete managed port profiles (matched by name)
  4. Delete managed networks (matched by VLAN ID)

Only resources whose names / VLAN IDs appear in the config YAML are touched.
Resources created outside this codebase are left untouched.

Run via scripts/ai-only-scripts/destroy-unifi-resources/run.
"""

import base64
import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

import yaml

DRY_RUN = os.environ.get("DRY_RUN", "true") != "false"
INFRA_DIR = os.environ["_INFRA_DIR"]

# ── Load config and credentials ───────────────────────────────────────────────

def load_config():
    """Return (ctrl_url, username, password, vlans_by_key, profiles_by_key)."""
    cfg_path = f"{INFRA_DIR}/unifi-pkg/_config/unifi-pkg.yaml"
    with open(cfg_path) as f:
        pub = yaml.safe_load(f)

    cp = pub["unifi-pkg"]["config_params"]

    # Find the entry with the controller URL
    ctrl_url = None
    for entry in cp.values():
        if isinstance(entry, dict) and "_provider_unifi_api_url" in entry:
            ctrl_url = entry["_provider_unifi_api_url"]
            break
    if not ctrl_url:
        sys.exit("ERROR: Could not find _provider_unifi_api_url in unifi-pkg.yaml")

    # Find the entry with vlans
    vlans = {}
    for entry in cp.values():
        if isinstance(entry, dict) and "vlans" in entry:
            vlans = entry["vlans"]
            break

    # Find the entry with port_profiles
    port_profiles = {}
    for entry in cp.values():
        if isinstance(entry, dict) and "port_profiles" in entry:
            port_profiles = entry["port_profiles"]
            break

    # Find the entry with devices
    devices = {}
    for entry in cp.values():
        if isinstance(entry, dict) and "devices" in entry:
            devices = entry["devices"]
            break

    # Load credentials from SOPS
    sec_path = f"{INFRA_DIR}/unifi-pkg/_config/unifi-pkg_secrets.sops.yaml"
    raw = subprocess.check_output(["sops", "--decrypt", sec_path], text=True)
    sec = yaml.safe_load(raw)

    # Credentials are under config_params at the pwy-homelab path
    creds = {}
    sec_cp = sec.get("unifi-pkg_secrets", {}).get("config_params", {})
    for entry in sec_cp.values():
        if isinstance(entry, dict) and "username" in entry:
            creds = entry
            break

    if not creds:
        sys.exit("ERROR: Could not find username/password in unifi-pkg_secrets")

    return ctrl_url, creds["username"], creds["password"], vlans, port_profiles, devices


# ── UniFi API client ──────────────────────────────────────────────────────────

class UnifiClient:
    def __init__(self, url, username, password):
        self.url = url.rstrip("/")
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.cookies = {}
        self.csrf_token = ""
        self._login(username, password)

    def _request(self, method, path, data=None, extra_headers=None):
        url = f"{self.url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        if extra_headers:
            headers.update(extra_headers)
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=self.ctx) as resp:
                for hdr in resp.headers.get_all("Set-Cookie") or []:
                    name, _, rest = hdr.partition("=")
                    self.cookies[name.strip()] = rest.split(";")[0].strip()
                body_bytes = resp.read()
                return json.loads(body_bytes) if body_bytes else {}, None
        except urllib.error.HTTPError as e:
            return None, f"HTTP {e.code}: {e.read().decode()[:300]}"

    def _login(self, username, password):
        _, err = self._request("POST", "/api/auth/login", {"username": username, "password": password})
        if err:
            sys.exit(f"ERROR: UniFi login failed: {err}")
        token = self.cookies.get("TOKEN", "")
        if token:
            try:
                parts = token.split(".")
                padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
                self.csrf_token = json.loads(base64.b64decode(padded)).get("csrfToken", "")
            except Exception:
                pass

    def get(self, path):
        result, err = self._request("GET", path)
        if err:
            sys.exit(f"ERROR GET {path}: {err}")
        return result.get("data", result)

    def put(self, path, data):
        result, err = self._request("PUT", path, data, {"X-Csrf-Token": self.csrf_token})
        return result, err

    def delete(self, path):
        result, err = self._request("DELETE", path, extra_headers={"X-Csrf-Token": self.csrf_token})
        return result, err


# ── Step 1: Clear portconf_id on device ports for managed profiles ─────────────

def clear_portconf_refs(client, managed_profile_ids):
    """Remove portconf_id = managed_profile_id from all device port overrides."""
    print("Step 1: Clearing port profile assignments from device ports ...")
    if not managed_profile_ids:
        print("  No managed profile IDs found — skipping")
        return

    devices = client.get("/proxy/network/api/s/default/stat/device")
    cleared_total = 0

    for device in devices:
        device_id   = device["_id"]
        device_name = device.get("name", device_id)
        overrides   = device.get("port_overrides", [])

        refs = [po for po in overrides if po.get("portconf_id", "") in managed_profile_ids]
        if not refs:
            continue

        print(f"  {device_name}: clearing portconf_id on {len(refs)} port(s)")
        if DRY_RUN:
            for po in refs:
                print(f"    port {po.get('port_idx','?')} (name={po.get('name','')})")
            continue

        # Rebuild overrides — keep name + number, drop portconf_id for managed profiles
        updated = []
        for po in overrides:
            entry = {"number": po["port_idx"]}
            if po.get("name"):
                entry["name"] = po["name"]
            if po.get("portconf_id", "") not in managed_profile_ids:
                if po.get("portconf_id"):
                    entry["portconf_id"] = po["portconf_id"]
            if po.get("native_networkconf_id"):
                entry["native_networkconf_id"] = po["native_networkconf_id"]
            if po.get("excluded_networkconf_ids"):
                entry["excluded_networkconf_ids"] = po["excluded_networkconf_ids"]
            updated.append(entry)

        _, err = client.put(
            f"/proxy/network/api/s/default/rest/device/{device_id}",
            {"port_overrides": updated},
        )
        if err:
            print(f"    SKIP {device_name}: {err[:80]}")
        else:
            cleared_total += len(refs)

    if not DRY_RUN:
        print(f"  Cleared portconf_id on {cleared_total} port(s)")


# ── Step 2: Clear excluded_networkconf_ids for managed networks ────────────────

def clear_excluded_network_refs(client, managed_network_ids):
    """Remove managed network IDs from device port excluded_networkconf_ids."""
    print("Step 2: Clearing excluded_networkconf_ids for managed networks ...")
    if not managed_network_ids:
        print("  No managed network IDs found — skipping")
        return

    devices = client.get("/proxy/network/api/s/default/stat/device")
    cleared_total = 0

    for device in devices:
        device_id   = device["_id"]
        device_name = device.get("name", device_id)
        overrides   = device.get("port_overrides", [])

        def has_ref(po):
            return bool(managed_network_ids & set(po.get("excluded_networkconf_ids", [])))

        refs = [po for po in overrides if has_ref(po)]
        if not refs:
            continue

        ref_count = sum(len(managed_network_ids & set(po.get("excluded_networkconf_ids", []))) for po in refs)
        print(f"  {device_name}: clearing {ref_count} network ref(s) on {len(refs)} port(s)")
        if DRY_RUN:
            continue

        updated = []
        for po in overrides:
            entry = {"number": po["port_idx"]}
            if po.get("name"):
                entry["name"] = po["name"]
            if po.get("portconf_id"):
                entry["portconf_id"] = po["portconf_id"]
            if po.get("native_networkconf_id"):
                entry["native_networkconf_id"] = po["native_networkconf_id"]
            excluded = [x for x in po.get("excluded_networkconf_ids", []) if x not in managed_network_ids]
            if excluded:
                entry["excluded_networkconf_ids"] = excluded
                if po.get("tagged_vlan_mgmt"):
                    entry["tagged_vlan_mgmt"] = po["tagged_vlan_mgmt"]
            if po.get("forward") and po["forward"] != "all":
                entry["forward"] = po["forward"]
            updated.append(entry)

        _, err = client.put(
            f"/proxy/network/api/s/default/rest/device/{device_id}",
            {"port_overrides": updated},
        )
        if err:
            print(f"    SKIP {device_name}: {err[:80]}")
        else:
            cleared_total += ref_count

    if not DRY_RUN:
        print(f"  Cleared {cleared_total} network reference(s)")


# ── Step 3: Delete managed port profiles ──────────────────────────────────────

def delete_port_profiles(client, managed_profile_names):
    """Delete port profiles whose names are in managed_profile_names."""
    print("Step 3: Deleting managed port profiles ...")
    all_profiles = client.get("/proxy/network/api/s/default/rest/portconf")

    to_delete = [p for p in all_profiles if p.get("name", "") in managed_profile_names]
    if not to_delete:
        print("  No managed port profiles found on controller — nothing to delete")
        return

    for profile in to_delete:
        name = profile["name"]
        pid  = profile["_id"]
        print(f"  DELETE port profile: {name!r} (id={pid})")
        if DRY_RUN:
            continue
        _, err = client.delete(f"/proxy/network/api/s/default/rest/portconf/{pid}")
        if err:
            print(f"    ERROR deleting {name!r}: {err}")
        else:
            print(f"    OK")


# ── Step 4: Delete managed networks (VLANs) ───────────────────────────────────

def delete_networks(client, managed_vlan_ids):
    """Delete networks whose vlan field matches a managed VLAN ID."""
    print("Step 4: Deleting managed networks (VLANs) ...")
    all_nets = client.get("/proxy/network/api/s/default/rest/networkconf")

    # Match by VLAN ID (integer)
    managed_vlan_id_set = {int(v) for v in managed_vlan_ids}
    to_delete = [n for n in all_nets if int(n.get("vlan", -1)) in managed_vlan_id_set]

    if not to_delete:
        print("  No managed networks found on controller — nothing to delete")
        return

    for net in to_delete:
        name = net.get("name", "?")
        nid  = net["_id"]
        vlan = net.get("vlan", "?")
        print(f"  DELETE network: {name!r} (VLAN {vlan}, id={nid})")
        if DRY_RUN:
            continue
        _, err = client.delete(f"/proxy/network/api/s/default/rest/networkconf/{nid}")
        if err:
            print(f"    ERROR deleting {name!r}: {err}")
        else:
            print(f"    OK")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ctrl_url, username, password, vlans, port_profiles, devices = load_config()

    managed_vlan_ids     = {str(v["vlan_id"]) for v in vlans.values()}
    managed_vlan_id_ints = {int(v["vlan_id"]) for v in vlans.values()}
    managed_profile_names = {p["name"] for p in port_profiles.values()}

    print(f"Controller : {ctrl_url}")
    print(f"Managed VLANs     : {sorted(managed_vlan_id_ints)}")
    print(f"Managed profiles  : {sorted(managed_profile_names)}")
    print("")

    print(f"Connecting to {ctrl_url} ...")
    client = UnifiClient(ctrl_url, username, password)
    print("Authenticated.\n")

    # Build managed profile ID set by fetching current profiles
    all_profiles = client.get("/proxy/network/api/s/default/rest/portconf")
    managed_profile_ids = {p["_id"] for p in all_profiles if p.get("name", "") in managed_profile_names}

    # Build managed network ID set by fetching current networks
    all_nets = client.get("/proxy/network/api/s/default/rest/networkconf")
    managed_network_ids = {n["_id"] for n in all_nets if int(n.get("vlan", -1)) in managed_vlan_id_ints}

    # Execute in dependency order
    clear_portconf_refs(client, managed_profile_ids)
    print("")
    clear_excluded_network_refs(client, managed_network_ids)
    print("")
    delete_port_profiles(client, managed_profile_names)
    print("")
    delete_networks(client, managed_vlan_ids)
    print("")

    if DRY_RUN:
        print("DRY-RUN complete — no changes were made.")
        print("Re-run with --apply to delete the resources shown above.")
    else:
        print("Done.")


if __name__ == "__main__":
    main()
