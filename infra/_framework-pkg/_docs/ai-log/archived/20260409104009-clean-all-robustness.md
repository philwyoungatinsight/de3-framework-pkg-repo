# Fix clean-all robustness: credential scoping, token matching, 404 handling

Three targeted fixes for edge cases that would break with optional or
multiple packages:

## Issue 1 — Proxmox token matching by path last-component (fragile)
Old: keyed `secret_tokens` by `path.split("/")[-1]` ("pve-1", "ms01-01").
Two packages with a secret path ending in the same leaf name would collide,
with the second silently overwriting the first.

New: build `endpoint_to_token` by cross-referencing each secret path against
`_ancestor_get(all_config_params, path, "_provider_proxmox_endpoint")`. Token
is then looked up by endpoint, which is guaranteed unique per physical node.

## Issue 2 — UniFi credential search too broad
Old: took the first secret entry anywhere with `username` + `password`. MaaS,
Proxmox, and other providers also store `username`/`password` in secrets. With
multiple optional packages the wrong credentials could be used.

New: credential search is scoped to the `ctrl_path` subtree (paths equal to or
under the path where `_provider_unifi_api_url` was found). VLANs and port
profiles are also scoped to this subtree.

## Issue 3 — DELETE on already-deleted resources prints ERROR (noisy on re-run)
404 from UniFi API on profile/network DELETE now prints "Already gone" instead
of "ERROR", making repeated clean-all runs produce clean output.
