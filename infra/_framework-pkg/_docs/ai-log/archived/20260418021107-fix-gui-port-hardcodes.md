# Fix GUI Port Hardcodes

## Summary

The embedded terminal in the GUI was broken because `_BACKEND_PORT` was hardcoded to `8000` while the app actually runs on port `9000`. The ports are defined once in `de3-gui-pkg.yaml` and flowed through env vars — every other hardcode was wrong.

## Changes

- **`homelab_gui.py`** — `_BACKEND_PORT`/`_FRONTEND_PORT` changed from literals `8000`/`8080` to `int(os.environ.get("HOMELAB_GUI_BACKEND/FRONTEND_PORT", "9000/9080"))`, matching `rxconfig.py`
- **`_application/de3-gui/run`** — `_read_config` fallbacks corrected from `"8080"`/`"8000"` to `"9080"`/`"9000"`
- **`tests/browser_test.py`** — default `--url` corrected from `localhost:8080` to `localhost:9080`
- **`tests/playbooks/smoke-test.yml`** — `gui_app_url`/`gui_api_url` vars changed from hardcoded `localhost:8080`/`8000` to env var lookups with correct defaults
- **`README.md`**, **`README.instructions.md`** — port references updated from 8080/8000 to 9080/9000
- **`de3-gui-pkg.yaml`** — YAML comments corrected (previously claimed "Default: 8080/8000" which referred to Reflex defaults, not project values)

## Root Cause

`_BACKEND_PORT = 8000` was present since the initial commit with a comment "must match rxconfig.py backend_port" — but `rxconfig.py` has always used `9000` (read from `HOMELAB_GUI_BACKEND_PORT` env var, which `de3-gui-pkg.yaml` sets to 9000). The terminal iframe URL pointed at the wrong port, so the WebSocket handshake failed silently and the terminal never connected.

## Notes

The source of truth is `de3-gui-pkg.yaml` → `frontend_port`/`backend_port`. The `run` script reads these and exports `HOMELAB_GUI_FRONTEND/BACKEND_PORT`. Every other file should read those env vars with matching fallbacks — no literal port numbers anywhere else.
