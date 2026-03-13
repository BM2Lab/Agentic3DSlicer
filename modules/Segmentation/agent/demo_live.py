"""
demo_live.py — Live demo: load CT abdomen, segment organs, rotate 3D view continuously.
Designed for screen recording. Does NOT quit — runs until user closes Slicer.
"""
import os, base64, json, tempfile, shutil, urllib.request, urllib.error
import slicer, SampleData, qt

SERVER_URL = "http://localhost:1527"
LABELS     = ["liver", "spleen", "left kidney", "right kidney"]
MODALITY   = "ct"

_rotation_timer = None   # keep reference to prevent GC

def log(msg):
    print(f"[demo] {msg}")
    slicer.app.processEvents()

def main():
    slicer.util.mainWindow().showMaximized()
    slicer.app.processEvents()

    log("Loading CTAAbdomenPanoramix…")
    try:
        volumeNode = SampleData.downloadSample("CTAAbdomenPanoramix")
    except Exception as e:
        slicer.util.errorDisplay(f"Failed to load volume: {e}"); return

    tmpdir = tempfile.mkdtemp(prefix="satseg_demo_")
    try:
        nifti_path = os.path.join(tmpdir, "volume.nii.gz")
        log("Exporting to NIfTI…")
        slicer.util.saveNode(volumeNode, nifti_path)
        with open(nifti_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        log(f"Sending to SAT server: {LABELS}…")
        payload = json.dumps({
            "volume_nifti": b64, "labels": LABELS, "modality": MODALITY
        }).encode()
        req = urllib.request.Request(f"{SERVER_URL}/segment", data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}")
        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "server error"))

        log("Decoding mask…")
        mask_path = os.path.join(tmpdir, "mask.nii.gz")
        with open(mask_path, "wb") as f:
            f.write(base64.b64decode(result["mask_nifti"]))

        labelmapNode = slicer.util.loadLabelVolume(mask_path)
        segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        segNode.SetName("CT_demo_SAT")
        segNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
            labelmapNode, segNode)
        slicer.mrmlScene.RemoveNode(labelmapNode)

        seg = segNode.GetSegmentation()
        for i, name in enumerate(LABELS):
            if i < seg.GetNumberOfSegments():
                seg.GetNthSegment(i).SetName(name)
        log(f"Imported {seg.GetNumberOfSegments()} segments: {LABELS}")

    except Exception as e:
        log(f"ERROR: {e}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        slicer.util.errorDisplay(str(e)); return
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ---- Set up 3D view ----
    log("Building 3D surface…")
    slicer.app.layoutManager().setLayout(
        slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
    segNode.CreateClosedSurfaceRepresentation()
    segNode.GetDisplayNode().SetVisibility3D(True)

    view3d = slicer.app.layoutManager().threeDWidget(0).threeDView()
    view3d.resetFocalPoint()
    slicer.app.processEvents()

    # ---- Start continuous rotation ----
    log("Starting continuous rotation…  (close Slicer window to stop)")
    _start_rotation(view3d)

def _start_rotation(view3d):
    global _rotation_timer
    rw = view3d.renderWindow()
    renderer = rw.GetRenderers().GetFirstRenderer()
    camera = renderer.GetActiveCamera()

    def _tick():
        camera.Azimuth(3)
        renderer.ResetCameraClippingRange()
        rw.Render()

    _rotation_timer = qt.QTimer()
    _rotation_timer.setInterval(50)   # 20 fps × 3° = ~60°/s
    _rotation_timer.timeout.connect(_tick)
    _rotation_timer.start()
    log("Rotation running.")

qt.QTimer.singleShot(500, main)
