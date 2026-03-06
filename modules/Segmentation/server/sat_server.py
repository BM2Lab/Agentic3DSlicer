"""
sat_server.py — SAT Inference HTTP Server
Port: 1527 (same convention as SlicerNNInteractive)

Endpoints:
    GET  /health    → {"status": "ok", "model": "SAT-Nano"}
    POST /segment   → accepts JSON, returns JSON

POST /segment request body:
    {
        "volume_nifti": "<base64-encoded .nii.gz bytes>",
        "labels":       ["liver", "spleen", ...],
        "modality":     "ct" | "mr" | "pet",
        "dataset":      "custom"   (optional, default "custom")
    }

POST /segment response:
    {
        "status":     "ok",
        "mask_nifti": "<base64-encoded combined seg .nii.gz bytes>"
    }

    on error:
    {
        "status":  "error",
        "message": "<description>"
    }

Usage:
    python sat_server.py              # runs on 0.0.0.0:1527
    python sat_server.py --port 1527  # explicit port
"""

import os
import sys
import base64
import tempfile
import shutil
import argparse
import logging

from flask import Flask, request, jsonify

# sat_inference.py lives one directory up
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sat_inference import run_sat_inference

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return jsonify({"status": "ok", "model": "SAT-Nano"})


# ---------------------------------------------------------------------------
# Segmentation endpoint
# ---------------------------------------------------------------------------

@app.post("/segment")
def segment():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

    # --- Validate required fields ---
    missing = [k for k in ("volume_nifti", "labels", "modality") if k not in data]
    if missing:
        return jsonify({"status": "error", "message": f"Missing fields: {missing}"}), 400

    labels = data["labels"]
    modality = data["modality"].lower()
    dataset = data.get("dataset", "custom")

    if not isinstance(labels, list) or not labels:
        return jsonify({"status": "error", "message": "'labels' must be a non-empty list"}), 400

    # --- Decode input NIfTI ---
    try:
        nifti_bytes = base64.b64decode(data["volume_nifti"])
    except Exception as e:
        return jsonify({"status": "error", "message": f"base64 decode failed: {e}"}), 400

    # --- Write to temp directory ---
    tmpdir = tempfile.mkdtemp(prefix="satseg_")
    try:
        input_nifti = os.path.join(tmpdir, "input.nii.gz")
        out_dir     = os.path.join(tmpdir, "output")
        os.makedirs(out_dir)

        with open(input_nifti, "wb") as f:
            f.write(nifti_bytes)

        log.info(f"Received segment request: labels={labels}, modality={modality}")

        # --- Run SAT inference ---
        seg_path = run_sat_inference(
            image_path=input_nifti,
            labels=labels,
            modality=modality,
            out_dir=out_dir,
            dataset_name=dataset,
        )

        # --- Read and encode result ---
        with open(seg_path, "rb") as f:
            mask_b64 = base64.b64encode(f.read()).decode("utf-8")

        log.info(f"Inference done → {seg_path}")
        return jsonify({"status": "ok", "mask_nifti": mask_b64})

    except Exception as e:
        log.error(f"Inference error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=1527)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    log.info(f"Starting SAT inference server on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, threaded=False)
