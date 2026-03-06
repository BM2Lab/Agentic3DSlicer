# Segmentation Module — Implementation Plan

## Architecture Overview

```
┌─────────────────────────────────────┐      HTTP / JSON      ┌──────────────────────────────┐
│        3D Slicer (client)           │ ◄───────────────────► │   SAT Inference Server       │
│                                     │    localhost:1527      │                              │
│  SATSeg scripted module             │                        │  Flask app wrapping SAT      │
│  ├── UI: text prompt input          │  POST /segment         │  ├── accepts NIfTI volume    │
│  ├── Volume → NIfTI export          │  ─────────────────►    │  ├── runs SAT inference      │
│  ├── Receive mask → labelmap node   │  ◄─────────────────    │  └── returns NIfTI mask      │
│  └── Segment Editor integration     │  mask NIfTI (bytes)    │                              │
└─────────────────────────────────────┘                        └──────────────────────────────┘
```

## Phase 1 — Scripted Module Skeleton (current)

**Goal:** Confirm the Slicer module loading pipeline works end-to-end before any ML work.

Tasks:
- [x] Create `SATSeg/SATSeg.py` — minimal ScriptedLoadableModule with a UI panel
- [x] Load it into Slicer via `--additional-module-paths`
- [x] Confirm module appears in Slicer's module menu and widget renders

**Key Slicer facts:**
- Scripted modules live in a folder named after the module (e.g. `SATSeg/SATSeg.py`)
- Load with: `Slicer --additional-module-paths /path/to/SATSeg`
- Module class must inherit `ScriptedLoadableModule`; widget from `ScriptedLoadableModuleWidget`

---

## Phase 2 — SAT Model Setup

**Goal:** Get SAT running locally and producing NIfTI segmentation masks.

Tasks:
- [x] Clone SAT repo into `modules/Segmentation/SAT/`
- [x] Create conda/venv environment with: torch, MONAI 1.1.0, transformers 4.21.3
- [x] Install custom `dynamic-network-architectures` from SAT repo
- [x] Download SAT-Nano checkpoint from Hugging Face
- [x] Write `sat_inference.py` — takes NIfTI path + text label list → outputs mask NIfTI
- [x] Verify output on a sample MRHead volume (~7s on RTX 5090)

**SAT inference inputs:**
- Image: NIfTI file path
- Labels: list of anatomical text strings (e.g. `["liver", "spleen"]`)
- Modality: "MR" | "CT" | "PET"
- Dataset name: required by SAT's JSONL format

---

## Phase 3 — Inference Server

**Goal:** Wrap SAT in a stateless HTTP server Slicer can call.

Tasks:
- [x] Write `server/sat_server.py` — Flask app on port 1527
- [x] `POST /segment` endpoint:
  - Accepts: `{volume_nifti: <base64>, labels: [...], modality: "MR"}`
  - Returns: `{mask_nifti: <base64>, status: "ok"}`
- [x] Add `/health` endpoint for connection check
- [x] Write `server/start_server.sh` — activates env and launches Flask

**Bugs fixed during Phase 3:**
- `sat_inference.py` missing `--text_encoder ours` arg → `KeyError: None` in Text_Encoder
- JSONL written inside `out_dir` → `shutil.SameFileError` when SAT copies it in

---

## Phase 4 — Slicer Client Module

**Goal:** Full integration — volume out, mask in, visualized in Slicer.

Tasks:
- [x] Extend `SATSeg.py` UI:
  - Server URL field (default `http://localhost:1527`)
  - Text prompt input (comma-separated anatomical labels)
  - Modality selector (MR / CT / PET)
  - "Run Segmentation" button
  - Status label
- [x] Logic layer:
  - Export selected volume node → temp NIfTI (`slicer.util.saveNode`)
  - POST to server (base64 NIfTI, urllib)
  - Decode response mask NIfTI → labelmap node (`slicer.util.loadLabelVolume`)
  - Show in slice views (`slicer.util.setSliceViewerLayers`)
- [x] Connection test button (`/health` ping)

---

## Phase 5 — Polish

- [x] 3D visualization — "Show 3D" button calls `CreateClosedSurfaceRepresentation()`, switches to 3D layout
- [x] Multi-label support — labelmap imported into `vtkMRMLSegmentationNode` via `ImportLabelmapToSegmentationNode`; segments renamed from label list
- [x] Save/load server config — persisted via `slicer.app.userSettings()` key `SATSeg/serverURL`
- [x] Error handling — step-by-step `statusCallback`, run button disabled during inference, indeterminate progress bar, `errorDisplay` on failure
- [x] Auto layout switch — Four-Up after segmentation, 3D-only on Show 3D

---

## Notes

- SAT requires 8+ A100-80GB for training; inference on single GPU (even smaller) should work
  for SAT-Nano with reduced batch size
- SlicerNNInteractive uses port 1527 + HTTP — adopting same convention
- Slicer's bundled Python cannot install heavy ML deps → server runs in separate environment
- NIfTI is the natural exchange format (Slicer ↔ SAT both speak it natively)
