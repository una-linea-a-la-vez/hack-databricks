#!/usr/bin/env bash
# Start the Gate API and the VR dev server together, and (if a Quest is
# attached over USB) forward port 5173 so the headset can open
# http://localhost:5173 — which counts as a secure context for WebXR.
set -euo pipefail

cd "$(dirname "$0")"

# Install from requirements.txt, and check what is installed rather than whether the folder
# exists: an install cut short with Ctrl+C left a .venv without uvicorn that was never repaired.
# databricks-sdk (bridge auth with the CLI profile) and python-multipart (voice upload) matter.
[ -x gate/.venv/bin/python ] || python3 -m venv gate/.venv
if ! gate/.venv/bin/python -c "import uvicorn, fastapi, httpx, multipart, dotenv, databricks.sdk" 2>/dev/null; then
  echo "installing gate/requirements.txt into gate/.venv"
  gate/.venv/bin/pip install -q -r gate/requirements.txt
fi
[ -d vr/node_modules ] || (cd vr && npm install)

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# .env first: exporting the default below before reading it made the gate ignore the
# BRIDGE_URL in .env (python-dotenv never overrides an exported variable), so a "live"
# setup silently talked to a local simulator instead.
if [ -f .env ]; then set -a; . ./.env; set +a; fi

# The agent lab bridge: the Databricks App in production (BRIDGE_URL in .env), or the
# hack-databricks repo locally on port 8010 so it does not collide with the gate.
export BRIDGE_URL="${BRIDGE_URL:-http://127.0.0.1:8010}"

gate/.venv/bin/python -m uvicorn main:app --app-dir gate --host 0.0.0.0 --port 8000 &

until curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; do sleep 0.3; done
echo "gate api  → http://127.0.0.1:8000  (docs at /docs)"
# Ask the gate, not the bridge: a Databricks App answers an unauthenticated curl with a
# login redirect; the gate carries the credentials (DATABRICKS_CONFIG_PROFILE or BRIDGE_TOKEN).
curl -s http://127.0.0.1:8000/health/full | gate/.venv/bin/python -c '
import json, sys
a = json.load(sys.stdin)["agent"]
state = "connected" if a["ok"] else "NOT reachable: %s" % a.get("detail")
print("agent lab → %s  (%s, mode %s)" % (a["url"], state, a.get("mode")))
' 2>/dev/null || echo "agent lab → $BRIDGE_URL  (could not ask the gate)"
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "voice     → OPENAI_API_KEY missing in .env: hold-to-ask stays disabled"
fi

if command -v adb >/dev/null && [ -n "$(adb devices | sed -n '2p')" ]; then
  adb reverse tcp:5173 tcp:5173 && echo "quest      → open http://localhost:5173/?xr=1 in the headset browser (web: same URL on this Mac)"
else
  echo "no adb device; for the headset use a tunnel or HTTPS=1 npm run dev"
fi

(cd vr && npm run dev) &
wait
