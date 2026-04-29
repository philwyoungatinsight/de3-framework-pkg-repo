# Plan: maas-bash-script-for-ms01-02

## Objective

Write a single self-contained bash script at
`config/tech-debt/maas-manul-setup/maas-setup.ms01-02.bash`
that drives ms01-02 through the full MaaS lifecycle (New → Commissioning → Ready →
Allocated → Deploying → Deployed) using the MaaS REST API directly — no Ansible,
no Terraform. When any phase fails, revert to the prior state and retry without
restarting from the beginning. This script is the ONLY tool used to iterate on
ms01-02 until deployment succeeds.

## Context

**Machine: ms01-02**
- MaaS server: `10.0.10.11:5240`
- PXE MAC: `38:05:25:31:81:10`
- Power type: AMT, address `10.0.11.11`, port `16993`
- `mgmt_wake_via_plug: true` — AMT loses standby when fully off; smart plug bounce restores it
- Smart plug: Tapo P125 at `192.168.2.105`, proxy at `http://10.0.10.11:7050`
- Deploy OS: `custom / rocky-9`
- Provisioning IP: `10.0.12.239` (DHCP, may vary)
- Cloud public IP: `10.0.10.117`

**Config source:** `infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml` +
`infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg_secrets.sops.yaml`

**Secrets structure** (relevant keys under `pwy-home-lab-pkg_secrets.config_params`):
- `pwy-home-lab-pkg/_stack/maas/pwy-homelab/.power_params_json`: MaaS API key (3-part OAuth)
  — OR — fetch fresh from server: `ssh ubuntu@10.0.10.11 "sudo snap run maas apikey --username admin"`
- `pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-02`:
  - `power_user` — AMT username
  - `power_pass` — AMT password
  - `smart_plug_username` — Tapo account email
  - `smart_plug_password` — Tapo account password

**MaaS API auth:** OAuth 1.0a PLAINTEXT. API key format: `consumer_key:token_key:token_secret`.
Authorization header:
```
OAuth realm="",oauth_consumer_key="<ck>",oauth_token="<tk>",oauth_signature_method="PLAINTEXT",oauth_timestamp="<ts>",oauth_nonce="<nonce>",oauth_version="1.0",oauth_signature="&<ts>"
```
Use `curl -s -H "Authorization: $AUTH_HEADER"` throughout.

**Smart plug proxy:** `POST http://10.0.10.11:7050/power/on?host=192.168.2.105&type=tapo`
and `/power/off`. Note: proxy uses Tapo credentials from its own config file — no need
to pass credentials in the request.

**MaaS machine query:** `GET /MAAS/api/2.0/machines/?hostname=ms01-02` returns a list.
Parse `.[] | {system_id, status_name, power_state}`.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `config/tech-debt/maas-manul-setup/maas-setup.ms01-02.bash` — create

Full script layout:

```
#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# CONFIG — read from SOPS YAML at runtime
# ============================================================
# All values loaded from config/SOPS at startup. Nothing hardcoded here
# except the paths to the config files.

GIT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
source "$GIT_ROOT/set_env.sh"

MAAS_SERVER="10.0.10.11"
MAAS_PORT="5240"
MAAS_API="http://${MAAS_SERVER}:${MAAS_PORT}/MAAS/api/2.0"

MACHINE_NAME="ms01-02"
PXE_MAC="38:05:25:31:81:10"
DEPLOY_OSYSTEM="custom"
DEPLOY_DISTRO="rocky-9"
CLOUD_PUBLIC_IP="10.0.10.117"

SMART_PLUG_HOST="192.168.2.105"
SMART_PLUG_PROXY="http://${MAAS_SERVER}:7050"

AMT_HOST="10.0.11.11"
AMT_PORT="16993"

# Load secrets via SOPS
_load_secrets() {
    local secrets_file="$GIT_ROOT/infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg_secrets.sops.yaml"
    local decrypted
    decrypted=$(sops -d "$secrets_file")
    # MaaS API key — fetch fresh from server (most reliable)
    MAAS_API_KEY=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        ubuntu@"$MAAS_SERVER" "sudo snap run maas apikey --username admin 2>/dev/null")
    # AMT credentials
    AMT_USER=$(echo "$decrypted" | python3 -c "
import sys, yaml
d = yaml.safe_load(sys.stdin)
cp = d['pwy-home-lab-pkg_secrets']['config_params']
print(cp['pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-02']['power_user'])
")
    AMT_PASS=$(echo "$decrypted" | python3 -c "
import sys, yaml
d = yaml.safe_load(sys.stdin)
cp = d['pwy-home-lab-pkg_secrets']['config_params']
print(cp['pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-02']['power_pass'])
")
}

# ============================================================
# HELPERS
# ============================================================

# Build OAuth Authorization header from API key
_auth_header() {
    local ck tk ts
    IFS=: read -r ck tk ts <<< "$MAAS_API_KEY"
    local timestamp nonce
    timestamp=$(date +%s)
    nonce=$(cat /proc/sys/kernel/random/uuid | tr -d '-' | head -c 16)
    echo "OAuth realm=\"\",oauth_consumer_key=\"${ck}\",oauth_token=\"${tk}\",oauth_signature_method=\"PLAINTEXT\",oauth_timestamp=\"${timestamp}\",oauth_nonce=\"${nonce}\",oauth_version=\"1.0\",oauth_signature=\"&${ts}\""
}

_maas_get() {
    # _maas_get <path> — GET from MaaS API, returns JSON
    curl -sf -H "Authorization: $(_auth_header)" "${MAAS_API}${1}"
}

_maas_post() {
    # _maas_post <path> [form_data] — POST to MaaS API
    curl -sf -X POST -H "Authorization: $(_auth_header)" "${MAAS_API}${1}" ${2:+-d "$2"}
}

_maas_delete() {
    curl -sf -X DELETE -H "Authorization: $(_auth_header)" "${MAAS_API}${1}"
}

_get_system_id() {
    _maas_get "/machines/?hostname=${MACHINE_NAME}" | \
        python3 -c "import sys,json; m=json.load(sys.stdin); print(m[0]['system_id'] if m else '')" 2>/dev/null
}

_get_status() {
    local sid="$1"
    _maas_get "/machines/${sid}/" | python3 -c "import sys,json; m=json.load(sys.stdin); print(m['status_name'])" 2>/dev/null
}

_log() { echo "[$(date '+%H:%M:%S')] $*"; }
_ok()  { echo "[$(date '+%H:%M:%S')] OK: $*"; }
_err() { echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2; }

# Poll until machine reaches target status (or one of multiple statuses)
# Usage: _wait_for_status <system_id> <timeout_secs> <status1> [status2 ...]
_wait_for_status() {
    local sid="$1" timeout="$2"; shift 2
    local targets=("$@")
    local elapsed=0 interval=10 current
    while (( elapsed < timeout )); do
        current=$(_get_status "$sid")
        for t in "${targets[@]}"; do
            if [[ "$current" == "$t" ]]; then
                _ok "Machine reached: $current"
                return 0
            fi
        done
        # Fail fast on terminal failure states
        if [[ "$current" == *"Failed"* || "$current" == "Broken" ]]; then
            _err "Machine entered failure state: $current"
            return 1
        fi
        _log "  Status: $current — waiting... (${elapsed}s/${timeout}s)"
        sleep "$interval"
        (( elapsed += interval ))
    done
    _err "Timed out after ${timeout}s waiting for: ${targets[*]} (last: $current)"
    return 1
}

# Bounce smart plug: off 10s on — restores AMT standby power
_bounce_plug() {
    _log "Bouncing smart plug (off→10s→on) to restore AMT standby..."
    curl -sf -X POST "${SMART_PLUG_PROXY}/power/off?host=${SMART_PLUG_HOST}&type=tapo" > /dev/null || true
    sleep 10
    curl -sf -X POST "${SMART_PLUG_PROXY}/power/on?host=${SMART_PLUG_HOST}&type=tapo" > /dev/null || true
    _log "Plug bounced. Waiting 30s for AMT to respond..."
    sleep 30
}

# Poll AMT port until reachable
_wait_for_amt() {
    local timeout="${1:-120}" elapsed=0
    while (( elapsed < timeout )); do
        if nc -zw3 "$AMT_HOST" "$AMT_PORT" 2>/dev/null; then
            _ok "AMT is reachable at ${AMT_HOST}:${AMT_PORT}"
            return 0
        fi
        _log "  AMT not reachable yet... (${elapsed}s/${timeout}s)"
        sleep 5; (( elapsed += 5 ))
    done
    _err "AMT unreachable after ${timeout}s"
    return 1
}

# Ensure AMT is reachable (bounce plug if not)
_ensure_amt() {
    if nc -zw3 "$AMT_HOST" "$AMT_PORT" 2>/dev/null; then
        _ok "AMT reachable"
        return 0
    fi
    _log "AMT unreachable — bouncing plug to restore standby power"
    _bounce_plug
    _wait_for_amt 120
}

# ============================================================
# PHASE FUNCTIONS
# ============================================================
# Each function:
#   1. Checks if already in target state → short-circuit
#   2. Does the work
#   3. Waits for target state
#   4. On failure: reverts to prior state and returns 1

# --- PHASE: NEW ---
# Ensure machine is enrolled in MaaS (status = New or beyond)
phase_new() {
    _log "=== PHASE: new ==="
    local sid
    sid=$(_get_system_id)
    if [[ -n "$sid" ]]; then
        local status
        status=$(_get_status "$sid")
        _ok "Machine already enrolled: system_id=$sid status=$status"
        echo "$sid"
        return 0
    fi
    _log "Machine not found in MaaS — triggering PXE enlistment via plug bounce + AMT"
    _ensure_amt
    # MaaS auto-enlists on PXE boot. Use AMT to set PXE boot override + power on.
    # The machine will PXE boot → run the enlistment kernel → appear as New.
    # MaaS AMT driver: maas machine power-on <sid> — but machine has no sid yet.
    # So: use wsman directly (or rely on AMT through MaaS after manual enroll).
    # Simplest approach: if machine has been deleted, bounce plug + poll for appearance.
    _bounce_plug
    _log "Waiting up to 5min for ms01-02 to appear in MaaS..."
    local timeout=300 elapsed=0
    while (( elapsed < timeout )); do
        sid=$(_get_system_id)
        if [[ -n "$sid" ]]; then
            _ok "Machine enrolled: system_id=$sid"
            echo "$sid"
            return 0
        fi
        sleep 15; (( elapsed += 15 ))
        _log "  Waiting for enrollment... (${elapsed}s/${timeout}s)"
    done
    _err "Machine did not appear in MaaS after ${timeout}s"
    return 1
}

# --- PHASE: COMMISSION ---
# Trigger commissioning and wait for Ready
phase_commission() {
    local sid="$1"
    _log "=== PHASE: commissioning (sid=$sid) ==="
    local status
    status=$(_get_status "$sid")

    # Short-circuit if already past commissioning
    case "$status" in
        Ready|Allocated|Deploying|Deployed) _ok "Already at $status — skipping commission"; return 0 ;;
        Commissioning) _log "Already commissioning — waiting for completion" ;;
        New)
            _log "Status=New — triggering commissioning"
            _ensure_amt
            _maas_post "/machines/${sid}/op-commission/" > /dev/null || {
                _err "Failed to trigger commissioning"
                return 1
            }
            _log "Commissioning triggered"
            ;;
        *)
            _err "Unexpected status for commission: $status"
            # Try to abort and reset
            _maas_post "/machines/${sid}/op-abort/" > /dev/null 2>&1 || true
            sleep 5
            return 1
            ;;
    esac

    # Wait up to 15 min for commissioning to complete
    _wait_for_status "$sid" 900 "Ready" || {
        _err "Commissioning did not reach Ready"
        # Revert: abort commissioning
        _log "Reverting: aborting commissioning..."
        _maas_post "/machines/${sid}/op-abort/" > /dev/null 2>&1 || true
        return 1
    }
}

# --- PHASE: ALLOCATE ---
phase_allocate() {
    local sid="$1"
    _log "=== PHASE: allocate (sid=$sid) ==="
    local status
    status=$(_get_status "$sid")

    case "$status" in
        Allocated|Deploying|Deployed) _ok "Already at $status — skipping allocate"; return 0 ;;
        Ready)
            _log "Status=Ready — allocating"
            # Set osystem/distro_series before allocate
            _maas_post "/machines/${sid}/" \
                "osystem=${DEPLOY_OSYSTEM}&distro_series=${DEPLOY_DISTRO}" > /dev/null || true
            # Allocate this specific machine by system_id
            _maas_post "/machines/op-allocate/" "system_id=${sid}" > /dev/null || {
                _err "Failed to allocate machine"
                return 1
            }
            _ok "Machine allocated"
            return 0
            ;;
        *)
            _err "Cannot allocate from status: $status"
            return 1
            ;;
    esac
}

# --- PHASE: DEPLOY ---
phase_deploy() {
    local sid="$1"
    _log "=== PHASE: deploy (sid=$sid) ==="
    local status
    status=$(_get_status "$sid")

    case "$status" in
        Deploying|Deployed) _ok "Already at $status — skipping deploy trigger"; return 0 ;;
        Allocated)
            _log "Status=Allocated — triggering deploy"
            _ensure_amt
            # Clear hwe_kernel for custom images (Rocky 9)
            _maas_post "/machines/${sid}/" "hwe_kernel=" > /dev/null 2>&1 || true
            # Deploy
            _maas_post "/machines/${sid}/op-deploy/" \
                "osystem=${DEPLOY_OSYSTEM}&distro_series=${DEPLOY_DISTRO}" > /dev/null || {
                _err "Failed to trigger deploy"
                return 1
            }
            _ok "Deploy triggered"
            ;;
        *)
            _err "Cannot deploy from status: $status"
            return 1
            ;;
    esac
}

# --- PHASE: WAIT DEPLOYED ---
phase_wait_deployed() {
    local sid="$1"
    _log "=== PHASE: wait for Deployed (sid=$sid) ==="
    local status
    status=$(_get_status "$sid")

    if [[ "$status" == "Deployed" ]]; then
        _ok "Already Deployed"
        return 0
    fi

    # Watch for Deploying → Deployed, with power-on watchdog every 5 min
    local timeout=1800 elapsed=0 interval=15
    while (( elapsed < timeout )); do
        status=$(_get_status "$sid")
        case "$status" in
            Deployed)
                _ok "=== DEPLOYED ==="
                return 0
                ;;
            "Failed deployment")
                _err "Deployment failed — reverting to New for retry"
                # Revert: release machine back to Ready, then delete + reboot to re-enlist
                _maas_post "/machines/${sid}/op-release/" > /dev/null 2>&1 || true
                return 1
                ;;
            Deploying)
                _log "  Deploying... (${elapsed}s/${timeout}s)"
                ;;
            *)
                _log "  Status: $status (${elapsed}s/${timeout}s)"
                ;;
        esac

        # Power-on watchdog: if machine goes off during deploy, bounce it
        if (( elapsed > 60 && elapsed % 300 == 0 )); then
            local power_state
            power_state=$(_maas_get "/machines/${sid}/" | \
                python3 -c "import sys,json; print(json.load(sys.stdin).get('power_state','?'))" 2>/dev/null)
            if [[ "$power_state" == "off" && "$status" == "Deploying" ]]; then
                _log "  Machine is off during deploy — bouncing plug to restore AMT and power on"
                _ensure_amt
                _maas_post "/machines/${sid}/op-power-on/" > /dev/null 2>&1 || true
            fi
        fi

        sleep "$interval"
        (( elapsed += interval ))
    done
    _err "Deploy timed out after ${timeout}s (status: $status)"
    _maas_post "/machines/${sid}/op-release/" > /dev/null 2>&1 || true
    return 1
}

# ============================================================
# MAIN LOOP
# ============================================================
main() {
    _log "Loading secrets..."
    _load_secrets

    local max_attempts=5 attempt=0
    while (( attempt < max_attempts )); do
        (( attempt++ ))
        _log "=== Attempt $attempt / $max_attempts ==="

        # Phase 1: ensure enrolled
        local sid
        sid=$(phase_new) || { _log "phase_new failed — retrying"; continue; }
        [[ -z "$sid" ]] && { _err "No system_id after phase_new"; continue; }
        _log "system_id: $sid"

        # Phase 2: commission
        phase_commission "$sid" || { _log "phase_commission failed — retrying from commission"; continue; }

        # Phase 3: allocate
        phase_allocate "$sid" || { _log "phase_allocate failed — retrying"; continue; }

        # Phase 4: deploy
        phase_deploy "$sid" || { _log "phase_deploy failed — retrying"; continue; }

        # Phase 5: wait for deployed
        phase_wait_deployed "$sid" && {
            _ok "=== ms01-02 DEPLOYED SUCCESSFULLY ==="
            _log "Cloud public IP: ${CLOUD_PUBLIC_IP}"
            exit 0
        }

        _log "Deployment failed on attempt $attempt — will retry (revert handled inside phase)"
    done

    _err "Failed after $max_attempts attempts"
    exit 1
}

main "$@"
```

## Execution Order

1. Create directory `config/tech-debt/maas-manul-setup/` (mkdir -p)
2. Write the script
3. `chmod +x` it
4. **Do NOT run the build or Ansible** — run the script directly:
   ```bash
   bash /home/pyoung/git/pwy-home-lab/config/tech-debt/maas-manul-setup/maas-setup.ms01-02.bash
   ```

## Notes on Revert Logic

Each phase reverts on failure:
- `phase_commission` failure → `op-abort` (puts machine back to New)
- `phase_wait_deployed` failure → `op-release` (puts machine back to Ready, can re-allocate)

If machine is deleted from MaaS entirely: `phase_new` handles re-enrollment via plug bounce.

The outer retry loop catches partial failures and restarts from the current state (not
from the beginning). Since each phase checks the current status and short-circuits if
already past that phase, retrying from the top is safe.

## Current State Note (at plan write time)

ms01-02 is currently `Allocated` (system_id=7te4kq). If the build was killed mid-flight,
it may have progressed further. The script handles this via the short-circuit logic in
each phase.

## Verification

```bash
bash config/tech-debt/maas-manul-setup/maas-setup.ms01-02.bash
```
Expected: exits 0, prints "ms01-02 DEPLOYED SUCCESSFULLY", SSH to 10.0.10.117 works as rocky.
