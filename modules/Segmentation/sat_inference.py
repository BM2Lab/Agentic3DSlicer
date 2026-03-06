"""
sat_inference.py — SAT (Segment Anything in 3D) inference wrapper

Provides run_sat_inference() for use by the Flask server (Phase 3).
Can also be run standalone for testing.

Usage (standalone):
    python sat_inference.py \
        --image /path/to/image.nii.gz \
        --labels "liver,spleen,left kidney" \
        --modality ct \
        --out_dir /tmp/sat_output

Outputs:
    <out_dir>/seg_<case_id>.nii.gz   — combined labelmap (label index per voxel)
    <out_dir>/<label>.nii.gz         — per-label binary mask
"""

import os
import sys
import json
import argparse
import tempfile
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relative to this file)
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
SAT_REPO    = _HERE / "SAT"
SAT_ENV     = _HERE / "sat-env"
SAT_PYTHON  = SAT_ENV / "bin" / "python"
CHECKPOINT  = _HERE / "checkpoints" / "SAT-Nano" / "Nano" / "nano.pth"
TEXT_ENC    = _HERE / "checkpoints" / "SAT-Nano" / "Nano" / "nano_text_encoder.pth"

# SAT model configuration (SAT-Nano defaults)
VISION_BACKBONE    = "UNET"
CROP_SIZE          = [288, 288, 96]
PATCH_SIZE         = [32, 32, 32]
MAX_QUERIES        = 256
BATCHSIZE_3D       = 1          # reduce to 1 for single-GPU server use


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_sat_inference(
    image_path: str,
    labels: list[str],
    modality: str,
    out_dir: str,
    dataset_name: str = "custom",
    gpu: str = "0",
) -> str:
    """
    Run SAT-Nano inference on a NIfTI volume.

    Args:
        image_path:   Absolute path to input NIfTI (.nii or .nii.gz).
        labels:       List of anatomical text labels, e.g. ["liver", "spleen"].
        modality:     "CT", "MR", or "PET" (case-insensitive).
        out_dir:      Directory where output NIfTI masks are written.
        dataset_name: Arbitrary dataset tag required by SAT JSONL format.
        gpu:          GPU id string, e.g. "0".

    Returns:
        Path to the combined segmentation NIfTI file
        (<out_dir>/seg_<case_id>.nii.gz).

    Raises:
        RuntimeError on inference failure.
    """
    image_path = str(Path(image_path).resolve())
    out_dir    = str(Path(out_dir).resolve())
    os.makedirs(out_dir, exist_ok=True)

    # --- Write temporary JSONL ---
    # Write JSONL outside out_dir to avoid SAT shutil.copy same-file conflict
    # (SAT copies the JSONL into out_dir itself)
    case_id   = Path(image_path).stem.replace(".nii", "")
    jsonl_tmp = Path(out_dir).parent / f"{case_id}_input.jsonl"
    entry = {
        "image":    image_path,
        "label":    labels,
        "modality": modality.lower(),
        "dataset":  dataset_name,
    }
    with open(jsonl_tmp, "w") as f:
        f.write(json.dumps(entry) + "\n")

    # --- Build subprocess command ---
    # Use run_inference_single_gpu.py which patches dist backend from nccl→gloo
    # (NCCL fails on RTX 5090 sm_120 with PyTorch cu124)
    cmd = [
        str(SAT_PYTHON),
        "run_inference_single_gpu.py",
        "--rcd_dir",                 out_dir,
        "--datasets_jsonl",          str(jsonl_tmp),
        "--checkpoint",              str(CHECKPOINT),
        "--text_encoder",            "ours",
        "--text_encoder_checkpoint", str(TEXT_ENC),
        "--vision_backbone",         VISION_BACKBONE,
        "--crop_size",               *[str(x) for x in CROP_SIZE],
        "--patch_size",              *[str(x) for x in PATCH_SIZE],
        "--max_queries",             str(MAX_QUERIES),
        "--batchsize_3d",            str(BATCHSIZE_3D),
        "--partial_load",            "true",
        "--text_encoder_partial_load", "true",
        "--dice",                    "false",
        "--nsd",                     "false",
        "--num_workers",             "2",
    ]

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = gpu

    print(f"[sat_inference] Running SAT-Nano on: {image_path}")
    print(f"[sat_inference] Labels: {labels}  Modality: {modality}")

    result = subprocess.run(
        cmd,
        cwd=str(SAT_REPO),
        env=env,
        capture_output=False,
        text=True,
    )

    # Clean up JSONL temp file
    try:
        jsonl_tmp.unlink(missing_ok=True)
    except Exception:
        pass

    if result.returncode != 0:
        raise RuntimeError(f"SAT inference failed (exit {result.returncode})")

    # --- Find output ---
    # SAT saves to <out_dir>/<dataset_name>/seg_<case_id>.nii.gz
    seg_file = Path(out_dir) / dataset_name / f"seg_{case_id}.nii.gz"
    if not seg_file.exists():
        # Fallback: recursive search
        candidates = list(Path(out_dir).rglob("seg_*.nii.gz"))
        if candidates:
            seg_file = candidates[0]
        else:
            raise RuntimeError(
                f"Inference completed but no seg_*.nii.gz found under {out_dir}"
            )

    print(f"[sat_inference] Output: {seg_file}")
    return str(seg_file)


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SAT-Nano inference")
    parser.add_argument("--image",    required=True,  help="Input NIfTI path")
    parser.add_argument("--labels",   required=True,  help="Comma-separated labels")
    parser.add_argument("--modality", default="ct",   help="CT / MR / PET")
    parser.add_argument("--out_dir",  default="/tmp/sat_output", help="Output directory")
    parser.add_argument("--gpu",      default="0",    help="GPU id")
    args = parser.parse_args()

    label_list = [l.strip() for l in args.labels.split(",")]

    out = run_sat_inference(
        image_path=args.image,
        labels=label_list,
        modality=args.modality,
        out_dir=args.out_dir,
        gpu=args.gpu,
    )
    print("Result:", out)
