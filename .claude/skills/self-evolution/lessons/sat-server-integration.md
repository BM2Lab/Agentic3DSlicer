# SAT Server Integration Lessons

**Phase:** 3 (Flask server) + 4 (Slicer client)
**Date:** 2026-03-05

---

## Bug 1: Missing `--text_encoder ours` in sat_inference.py

**Symptom:** `KeyError: None` in `SAT/model/text_encoder.py` line 48 (`Text_Encoder.__init__`).

**Cause:** `sat_inference.py` subprocess call was missing the `--text_encoder ours` argument. Without it, the argparse value is `None`, and `Text_Encoder` does a dict lookup with `None` as key.

**Fix:** Add to subprocess cmd list:
```python
"--text_encoder", "ours",
```
Valid values: `ours`, `medcpt`, `basebert`. SAT-Nano always uses `ours`.

---

## Bug 2: shutil.SameFileError — JSONL written inside out_dir

**Symptom:** `shutil.SameFileError: '/tmp/satseg_.../output/input_input.jsonl' and '...' are the same file`

**Cause:** `sat_inference.py` wrote the JSONL temp file to `Path(out_dir) / f"{case_id}_input.jsonl"`. SAT's inference script then tries to `shutil.copy` the JSONL into the same `out_dir`, producing a same-file collision.

**Fix:** Write JSONL to the *parent* of `out_dir`:
```python
jsonl_tmp = Path(out_dir).parent / f"{case_id}_input.jsonl"
```

---

## Phase 4: Slicer volume export to NIfTI

**Working pattern:**
```python
slicer.util.saveNode(volumeNode, "/tmp/volume.nii.gz")
```
Slicer auto-selects the NIfTI storage node based on the `.nii.gz` extension.

---

## Phase 4: Load mask NIfTI as labelmap

```python
labelmapNode = slicer.util.loadLabelVolume("/tmp/mask.nii.gz")
labelmapNode.SetName("my_seg")
slicer.util.setSliceViewerLayers(label=labelmapNode)
```

---

## Server startup

```bash
# From modules/Segmentation/
bash server/start_server.sh           # default port 1527
bash server/start_server.sh --port X  # custom port
```

The script activates `sat-env/`, `cd`s to `modules/Segmentation/`, and runs `server/sat_server.py`. The `cd` is critical so that `from sat_inference import run_sat_inference` resolves correctly.
