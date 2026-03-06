"""
eval_ct_abdomen.py — Evaluate SAT on CTAAbdomenPanoramix with labels: liver, spleen, left kidney, right kidney
Saves screenshot to agent/eval_ct_abdomen.png
"""
import os, base64, json, tempfile, shutil, urllib.request, urllib.error
import slicer, SampleData, qt

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(AGENT_DIR, "eval_ct_abdomen.png")
SERVER_URL = "http://localhost:1527"
LABELS = ["liver", "spleen", "left kidney", "right kidney"]
MODALITY = "ct"

errors = []

def log(msg):
    print(f"[eval_ct_abdomen] {msg}")
    slicer.app.processEvents()

def main():
    log("Downloading CTAAbdomenPanoramix…")
    try:
        volumeNode = SampleData.downloadSample("CTAAbdomenPanoramix")
    except Exception as e:
        errors.append(f"Load failed: {e}"); finish(); return

    tmpdir = tempfile.mkdtemp(prefix="satseg_ct_")
    try:
        nifti_path = os.path.join(tmpdir, "volume.nii.gz")
        log("Exporting to NIfTI…")
        slicer.util.saveNode(volumeNode, nifti_path)
        with open(nifti_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        log(f"POSTing labels={LABELS}…")
        payload = json.dumps({"volume_nifti": b64, "labels": LABELS, "modality": MODALITY}).encode()
        req = urllib.request.Request(f"{SERVER_URL}/segment", data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}")

        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "Unknown error"))

        mask_path = os.path.join(tmpdir, "mask.nii.gz")
        with open(mask_path, "wb") as f:
            f.write(base64.b64decode(result["mask_nifti"]))

        labelmapNode = slicer.util.loadLabelVolume(mask_path)
        segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        segNode.SetName("CT_abdomen_SAT")
        segNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapNode, segNode)
        slicer.mrmlScene.RemoveNode(labelmapNode)

        seg = segNode.GetSegmentation()
        for i, name in enumerate(LABELS):
            if i < seg.GetNumberOfSegments():
                seg.GetNthSegment(i).SetName(name)

        n = seg.GetNumberOfSegments()
        log(f"Imported {n} segment(s)")

        slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
        slicer.util.setSliceViewerLayers(background=volumeNode)
        segNode.CreateClosedSurfaceRepresentation()
        segNode.GetDisplayNode().SetVisibility3D(True)
        slicer.app.layoutManager().threeDWidget(0).threeDView().resetFocalPoint()
        slicer.app.processEvents()

    except Exception as e:
        errors.append(str(e)); log(f"ERROR: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    qt.QTimer.singleShot(3000, _screenshot_and_quit)

def _screenshot_and_quit():
    slicer.app.processEvents()
    pixmap = qt.QPixmap.grabWidget(slicer.util.mainWindow())
    pixmap.save(SCREENSHOT_PATH)
    log(f"Screenshot saved ({pixmap.width()}x{pixmap.height()} px) → {SCREENSHOT_PATH}")
    finish()

def finish():
    if errors:
        log("Errors: " + "; ".join(errors))
    else:
        log("Complete — no errors.")
    slicer.app.quit()

qt.QTimer.singleShot(1000, main)
