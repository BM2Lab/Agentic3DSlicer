# SAT Python Environment Setup

**Category:** Python Environment — SAT (Segment Anything in 3D)
**Severity:** High — each issue silently breaks inference or causes cryptic runtime errors
**Discovered:** 2026-03-05
**Context:** RTX 5090 (sm_120 Blackwell), single-GPU inference, SAT-Nano model

---

## uv — Create Isolated Env (No Conda Needed)

```bash
uv python install 3.10           # download Python 3.10
uv venv /path/to/sat-env --python 3.10

# Install into a specific venv:
VIRTUAL_ENV=/path/to/sat-env uv pip install <packages>
```

---

## PyTorch for RTX 5090 (sm_120 Blackwell)

**Problem:** PyTorch cu124 (2.6.0) only compiles kernels for sm_50..sm_90. RTX 5090 is Blackwell (sm_120). Basic ops work via PTX JIT, but transformer attention kernels and NCCL fail.

**Fix:** Use cu128 wheels (PyTorch 2.10+) which include sm_120 kernels:

```bash
VIRTUAL_ENV=/path/to/sat-env uv pip install torch torchvision \
  --index-url https://download.pytorch.org/whl/cu128 --reinstall
```

Verify:
```python
import torch
print(torch.__version__)                          # 2.10.0+cu128
print(torch.cuda.get_device_capability(0))        # (12, 0) for RTX 5090 — no warning
```

---

## NumPy Version Pin (MONAI 1.1.0 Compatibility)

**Problem:** `numpy>=2.0` removed `ndarray.ptp()`. MONAI 1.1.0 uses it in `Spacingd` transforms → `AttributeError: ptp was removed`.

**Fix:** Pin numpy **after** installing torch (torch 2.10 re-installs numpy 2.x):

```bash
VIRTUAL_ENV=/path/to/sat-env uv pip install "numpy<2.0"
# Settles on numpy==1.26.4
```

**Note:** Must re-run this after any `torch` upgrade — torch pulls numpy 2.x.

---

## torch.load weights_only (PyTorch 2.6+ Breaking Change)

**Problem:** PyTorch 2.6 changed `torch.load` default to `weights_only=True`. SAT checkpoints contain `numpy.core.multiarray.scalar` → `UnpicklingError`.

**Fix (monkey-patch at import time):**
```python
import torch
_orig = torch.load
def _load_unsafe(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _orig(*args, **kwargs)
torch.load = _load_unsafe
```

---

## NCCL Fails on RTX 5090 — Replace DDP with Identity Wrapper

**Problem:** `torch.nn.parallel.DistributedDataParallel.__init__` calls `_broadcast_coalesced` (CUDA) and NCCL — both fail on sm_120 with cu124.

**Fix:** Replace DDP with a no-op identity wrapper for single-GPU inference. Must patch **before** importing any module that uses DDP.

```python
import torch, torch.nn as _nn

class _NoDDP(_nn.Module):
    def __init__(self, module, *args, **kwargs):
        super().__init__()
        self.module = module
    def forward(self, *args, **kwargs):
        return self.module(*args, **kwargs)

_nn.parallel.DistributedDataParallel = _NoDDP
torch.nn.parallel.DistributedDataParallel = _NoDDP
```

Also replace `nccl` backend with `gloo` in `init_process_group`:
```python
import torch.distributed as _dist
_orig_init = _dist.init_process_group
def _gloo_init(*args, **kwargs):
    kwargs["backend"] = "gloo"
    return _orig_init(*args, **kwargs)
_dist.init_process_group = _gloo_init
```

Set these env vars **before** importing torch.distributed:
```python
import os
os.environ.setdefault("RANK", "0")
os.environ.setdefault("LOCAL_RANK", "0")
os.environ.setdefault("WORLD_SIZE", "1")
os.environ.setdefault("MASTER_ADDR", "127.0.0.1")
os.environ.setdefault("MASTER_PORT", "29501")
```

---

## transformers==4.21.3 — HuggingFace Hub URL Bug

**Problem:** Old transformers version builds relative (not absolute) URLs when downloading models → `MissingSchema: Invalid URL '/api/resolve-cache/...'`.

**Fix:** Pre-download required models to local disk using `huggingface_hub`:

```python
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="FremyCompany/BioLORD-2023-C",
    local_dir="/path/to/checkpoints/BioLORD-2023-C"
)
```

Then patch the hardcoded checkpoint path before the model loads:
```python
import model.knowledge_encoder as _ke
_orig_init = _ke.Knowledge_Encoder.__init__
def _patched_init(self, biolord_checkpoint=None):
    _orig_init(self, biolord_checkpoint="/path/to/BioLORD-2023-C")
_ke.Knowledge_Encoder.__init__ = _patched_init
```

---

## SAT Output Directory Structure

SAT saves results to:
```
<rcd_dir>/
└── <dataset>/                        # value of "dataset" field in JSONL
    ├── seg_<case_id>.nii.gz          # combined labelmap (int, one value per label)
    ├── img_<case_id>.nii.gz          # copy of input image
    └── seg_<case_id>/
        ├── liver.nii.gz              # per-label binary masks
        ├── kidney.nii.gz
        └── ...
```

Use `rglob("seg_*.nii.gz")` as fallback when the dataset name is unknown.

---

## SAT JSONL Input Format

```json
{"image": "/abs/path/img.nii.gz", "label": ["liver", "spleen"], "modality": "ct", "dataset": "custom"}
```

- `modality`: `"ct"`, `"mri"`, `"us"`, `"pet"` (lowercase)
- `dataset`: arbitrary string — becomes the output subdirectory name
- `label`: list of anatomical text strings SAT was trained on

---

## SAT-Nano Required Checkpoints

| File | Size | What |
|------|------|------|
| `Nano/nano.pth` | 1.4 GB | MaskFormer segmentation model |
| `Nano/nano_text_encoder.pth` | 423 MB | Knowledge Encoder (BioLORD-based) |
| `BioLORD-2023-C/` | ~440 MB | Base BERT for Knowledge Encoder (must be local) |

Download:
```python
from huggingface_hub import hf_hub_download, snapshot_download
hf_hub_download("zzh99/SAT", "Nano/nano.pth", local_dir="checkpoints/SAT-Nano")
hf_hub_download("zzh99/SAT", "Nano/nano_text_encoder.pth", local_dir="checkpoints/SAT-Nano")
snapshot_download("FremyCompany/BioLORD-2023-C", local_dir="checkpoints/BioLORD-2023-C")
```

`--text_encoder` arg value for SAT-Nano: `ours`

---

## Rules Summary

| Issue | Fix |
|-------|-----|
| RTX 5090 / Blackwell sm_120 PyTorch | Use cu128 wheels (torch 2.10+) |
| MONAI `ptp` error | Pin `numpy<2.0` after every torch install |
| `torch.load` UnpicklingError | Monkey-patch to set `weights_only=False` |
| DDP / NCCL crash on single GPU | Replace DDP with identity wrapper + use gloo backend |
| HuggingFace URL error (transformers 4.21.3) | Pre-download models locally; patch `__init__` |
| Unknown output path | Use `rglob("seg_*.nii.gz")` to scan results |

---

## Related

- `modules/Segmentation/SAT/` — SAT model source
- `modules/Segmentation/sat_inference.py` — working inference script with all patches applied
- `modules/Segmentation/SATSeg/SATSeg.py` — 3D Slicer module wrapping sat_inference.py
