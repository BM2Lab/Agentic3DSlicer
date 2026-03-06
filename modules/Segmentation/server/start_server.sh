#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# start_server.sh — Launch the SAT inference HTTP server
#
# Usage:
#   cd modules/Segmentation          # or anywhere, path is resolved
#   ./server/start_server.sh         # default port 1527
#   ./server/start_server.sh --port 9000
#
# The script activates the sat-env virtual environment that lives alongside
# this module (modules/Segmentation/sat-env/) then starts sat_server.py.
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEG_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$SEG_DIR/sat-env"

if [[ ! -f "$VENV/bin/activate" ]]; then
    echo "[ERROR] Virtual environment not found at: $VENV"
    echo "  Create it with: uv venv $VENV --python 3.10"
    exit 1
fi

echo "[INFO] Activating sat-env: $VENV"
# shellcheck source=/dev/null
source "$VENV/bin/activate"

echo "[INFO] Python: $(which python) ($(python --version))"

# Change to Segmentation root so sat_inference.py imports resolve correctly
cd "$SEG_DIR"

echo "[INFO] Starting SAT inference server..."
exec python server/sat_server.py "$@"
