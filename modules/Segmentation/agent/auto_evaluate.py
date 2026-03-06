"""
auto_evaluate.py — End-to-end SAT segmentation evaluation script for 3D Slicer.

Run via:
    /path/to/Slicer --python-script /path/to/auto_evaluate.py

What it does:
  1. Downloads the MRHead sample volume
  2. Posts it to the SAT server at localhost:1527 with labels ["brain stem", "cerebellum"]
  3. Imports the returned mask as a named segmentation node
  4. Builds 3D surface and switches to Four-Up layout
  5. Takes a screenshot of the main window
  6. Saves to agent/evaluation_screenshot.png
  7. Quits Slicer
"""

import os
import base64
import json
import tempfile
import shutil
import urllib.request
import urllib.error

import slicer
import SampleData
import qt

AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOT_PATH = os.path.join(AGENT_DIR, "evaluation_screenshot.png")
SERVER_URL = "http://localhost:1527"
LABELS = ["brain stem", "cerebellum"]
MODALITY = "mr"

errors = []


def log(msg):
    print(f"[auto_evaluate] {msg}")
    slicer.app.processEvents()


def main():
    # ------------------------------------------------------------------ #
    # 1. Health check                                                      #
    # ------------------------------------------------------------------ #
    log("Checking server health…")
    try:
        with urllib.request.urlopen(f"{SERVER_URL}/health", timeout=10) as r:
            health = json.loads(r.read())
            log(f"Server OK: {health}")
    except Exception as e:
        errors.append(f"Server not reachable: {e}")
        log(f"ERROR: {e}")
        finish()
        return

    # ------------------------------------------------------------------ #
    # 2. Load MRHead                                                       #
    # ------------------------------------------------------------------ #
    log("Downloading MRHead sample volume…")
    try:
        volumeNode = SampleData.downloadSample("MRHead")
        log(f"Volume loaded: {volumeNode.GetName()}")
    except Exception as e:
        errors.append(f"Failed to load MRHead: {e}")
        log(f"ERROR: {e}")
        finish()
        return

    # ------------------------------------------------------------------ #
    # 3. Export to NIfTI + POST to server                                  #
    # ------------------------------------------------------------------ #
    tmpdir = tempfile.mkdtemp(prefix="satseg_eval_")
    try:
        nifti_path = os.path.join(tmpdir, "volume.nii.gz")
        log("Exporting volume to NIfTI…")
        slicer.util.saveNode(volumeNode, nifti_path)

        with open(nifti_path, "rb") as f:
            volume_b64 = base64.b64encode(f.read()).decode("utf-8")

        payload = json.dumps({
            "volume_nifti": volume_b64,
            "labels":       LABELS,
            "modality":     MODALITY,
        }).encode("utf-8")

        log(f"POSTing to {SERVER_URL}/segment (labels={LABELS})…")
        req = urllib.request.Request(
            f"{SERVER_URL}/segment",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code}: {body}")

        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "Unknown server error"))

        log("Inference complete. Decoding mask…")
        mask_path = os.path.join(tmpdir, "mask.nii.gz")
        with open(mask_path, "wb") as f:
            f.write(base64.b64decode(result["mask_nifti"]))

        # ---------------------------------------------------------------- #
        # 4. Import as segmentation node                                    #
        # ---------------------------------------------------------------- #
        labelmapNode = slicer.util.loadLabelVolume(mask_path)
        segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        segNode.SetName("MRHead_SAT")
        segNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
            labelmapNode, segNode
        )
        slicer.mrmlScene.RemoveNode(labelmapNode)

        seg = segNode.GetSegmentation()
        for i, name in enumerate(LABELS):
            if i < seg.GetNumberOfSegments():
                seg.GetNthSegment(i).SetName(name)

        n_segs = seg.GetNumberOfSegments()
        log(f"Segmentation imported: {n_segs} segment(s)")

        # ---------------------------------------------------------------- #
        # 5. Layout + 3D surface                                            #
        # ---------------------------------------------------------------- #
        slicer.app.layoutManager().setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView
        )
        slicer.util.setSliceViewerLayers(foreground=volumeNode)

        log("Building 3D surface representation…")
        segNode.CreateClosedSurfaceRepresentation()
        segNode.GetDisplayNode().SetVisibility3D(True)
        slicer.app.layoutManager().threeDWidget(0).threeDView().resetFocalPoint()

        slicer.app.processEvents()
        qt.QTimer.singleShot(2000, _screenshot_and_quit)

    except Exception as e:
        errors.append(str(e))
        log(f"ERROR during segmentation: {e}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        finish()
    # tmpdir cleaned up after screenshot in _screenshot_and_quit
    finally:
        # Only clean up if we're not waiting for the timer
        if errors:
            shutil.rmtree(tmpdir, ignore_errors=True)


_tmpdir_to_clean = None


def _screenshot_and_quit():
    log(f"Saving screenshot to {SCREENSHOT_PATH}…")
    slicer.app.processEvents()
    pixmap = qt.QPixmap.grabWidget(slicer.util.mainWindow())
    pixmap.save(SCREENSHOT_PATH)
    log(f"Screenshot saved ({pixmap.width()}x{pixmap.height()} px)")
    finish()


def finish():
    if errors:
        log("Completed with errors:")
        for e in errors:
            log(f"  - {e}")
    else:
        log("Evaluation complete — no errors.")
    slicer.app.quit()


# Entry point — Slicer calls the script in module scope, so we schedule
# main() after the event loop starts to allow full Slicer initialisation.
qt.QTimer.singleShot(1000, main)
