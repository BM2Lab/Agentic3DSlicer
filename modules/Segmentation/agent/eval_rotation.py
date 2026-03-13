"""
eval_rotation.py — Load CT abdomen, segment organs, rotate 3D view 360°, capture 4 frames.
Saves frames to agent/rotation_frames/ and quits.
"""
import os, sys, base64, json, tempfile, shutil, urllib.request, urllib.error
import slicer, SampleData, qt

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
FRAMES_DIR = os.path.join(AGENT_DIR, "rotation_frames")

SERVER_URL = "http://localhost:1527"
LABELS = ["liver", "spleen", "left kidney", "right kidney"]
MODALITY = "ct"

_timer_ref = None   # prevent GC of QTimer

def log(msg):
    print(f"[eval_rotation] {msg}")
    slicer.app.processEvents()

def main():
    log("Downloading CTAAbdomenPanoramix…")
    try:
        volumeNode = SampleData.downloadSample("CTAAbdomenPanoramix")
    except Exception as e:
        log(f"ERROR loading volume: {e}"); slicer.app.quit(); return

    tmpdir = tempfile.mkdtemp(prefix="satseg_rot_")
    try:
        nifti_path = os.path.join(tmpdir, "volume.nii.gz")
        slicer.util.saveNode(volumeNode, nifti_path)
        with open(nifti_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        log(f"Segmenting: {LABELS}…")
        payload = json.dumps({"volume_nifti": b64, "labels": LABELS, "modality": MODALITY}).encode()
        req = urllib.request.Request(f"{SERVER_URL}/segment", data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}")
        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "server error"))

        mask_path = os.path.join(tmpdir, "mask.nii.gz")
        with open(mask_path, "wb") as f:
            f.write(base64.b64decode(result["mask_nifti"]))

        labelmapNode = slicer.util.loadLabelVolume(mask_path)
        segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        segNode.SetName("CT_rotation_SAT")
        segNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapNode, segNode)
        slicer.mrmlScene.RemoveNode(labelmapNode)
        seg = segNode.GetSegmentation()
        for i, name in enumerate(LABELS):
            if i < seg.GetNumberOfSegments():
                seg.GetNthSegment(i).SetName(name)

        log(f"Imported {seg.GetNumberOfSegments()} segment(s)")

    except Exception as e:
        log(f"ERROR: {e}"); shutil.rmtree(tmpdir, ignore_errors=True)
        slicer.app.quit(); return
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    log("Setting layout…")
    slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
    slicer.util.setSliceViewerLayers(background=volumeNode)
    log("Building 3D surface…")
    segNode.CreateClosedSurfaceRepresentation()
    log("Enabling 3D visibility…")
    segNode.GetDisplayNode().SetVisibility3D(True)
    slicer.app.layoutManager().threeDWidget(0).threeDView().resetFocalPoint()
    slicer.app.processEvents()
    log("Setup done. Starting rotation in 2s…")

    # Rotate 90° x 4 stops, take a screenshot at each stop, then quit
    qt.QTimer.singleShot(2000, _rotate_and_capture)

# Standard view axes for 4-stop rotation
# rotateToViewAxis: 0=Left, 1=Right, 2=Posterior, 3=Anterior, 4=Inferior, 5=Superior
_VIEW_AXES = [3, 0, 2, 1]   # Anterior → Left → Posterior → Right
_VIEW_NAMES = ["anterior", "left", "posterior", "right"]
_capture_state = {"stop": 0}

def _vtk_screenshot(render_window, path):
    """Capture a render window to PNG using VTK (works headless)."""
    import vtk
    wti = vtk.vtkWindowToImageFilter()
    wti.SetInput(render_window)
    wti.SetScale(1)
    wti.ReadFrontBufferOff()
    wti.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(path)
    writer.SetInputConnection(wti.GetOutputPort())
    writer.Write()

def _rotate_and_capture():
    """Snap to next view axis, render, capture via VTK, repeat 4× then quit."""
    import os
    state = _capture_state
    stop = state["stop"]

    if stop >= len(_VIEW_AXES):
        log(f"All {len(_VIEW_AXES)} frames saved to {FRAMES_DIR}/")
        slicer.app.quit()
        return

    os.makedirs(FRAMES_DIR, exist_ok=True)
    view_name = _VIEW_NAMES[stop]
    log(f"Stop {stop}/{len(_VIEW_AXES)}: view={view_name}, saving screenshot…")

    view3d = slicer.app.layoutManager().threeDWidget(0).threeDView()
    # Snap camera to standard axis (fast — no incremental rendering)
    view3d.rotateToViewAxis(_VIEW_AXES[stop])
    # Force a single render
    view3d.renderWindow().Render()

    path = os.path.join(FRAMES_DIR, f"frame_{stop:02d}_{view_name}.png")
    _vtk_screenshot(view3d.renderWindow(), path)
    log(f"  saved {path}")

    state["stop"] += 1
    qt.QTimer.singleShot(300, _rotate_and_capture)

qt.QTimer.singleShot(1000, main)
