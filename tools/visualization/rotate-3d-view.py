"""
Tool:        rotate-3d-view.py
Category:    visualization
Tags:        rotation, 3D view, yaw, pitch, roll, animate, camera, orbit, headless, vtk, screenshot
Description: Rotate the 3D view programmatically. Provides step, animated, and
             standard-view-snap approaches. Includes VTK-based screenshot (works headless).
Usage:       Load via importlib (hyphen in name prevents direct import):
                 import importlib.util
                 spec = importlib.util.spec_from_file_location("r3d", "/path/to/rotate-3d-view.py")
                 mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
Version:     1.1
Verified:    2026-03-06  (Slicer 5.10.0)

Built-in rotation methods on qMRMLThreeDView:
    YawLeft()  / YawRight()   — horizontal orbit (1 render per call — SLOW in headless)
    PitchUp()  / PitchDown()  — vertical tilt
    RollLeft() / RollRight()  — in-plane spin
    setPitchRollYawIncrement(degrees) — set step size (default 5°)
    rotateToViewAxis(axis)    — FAST snap: 0=L 1=R 2=Post 3=Ant 4=Inf 5=Sup

INTERACTIVE ROTATION (live display) — VERIFIED:
    Use VTK camera directly. YawLeft() + renderWindow().Render() does NOT produce
    visible rotation on a live display.

        rw = view3d.renderWindow()
        renderer = rw.GetRenderers().GetFirstRenderer()
        camera = renderer.GetActiveCamera()
        def _tick():
            camera.Azimuth(3)
            renderer.ResetCameraClippingRange()
            rw.Render()
        timer = qt.QTimer(); timer.setInterval(50)
        timer.timeout.connect(_tick); timer.start()

HEADLESS SCREENSHOT SEQUENCES — VERIFIED:
    Use rotateToViewAxis() + renderWindow().Render() + vtk_screenshot().
    YawLeft() is slow on Xvfb (one full render per call).

LAYOUT CONSTANTS: SlicerLayoutOneUp3DView, SlicerLayoutFourUpView
    (SlicerLayout3DView does NOT exist — use SlicerLayoutOneUp3DView)
"""

import qt
import slicer


def get_3d_view(widget_index=0):
    """Return the qMRMLThreeDView for the given layout widget index."""
    return slicer.app.layoutManager().threeDWidget(widget_index).threeDView()


def rotate_step(axis="yaw", direction="left", degrees=5, widget_index=0):
    """
    Rotate the 3D view by `degrees` in one shot.

    axis:      "yaw" | "pitch" | "roll"
    direction: "left"/"right" for yaw&roll, "up"/"down" for pitch
    degrees:   angle in degrees (sets the increment temporarily)
    """
    view = get_3d_view(widget_index)
    view.setPitchRollYawIncrement(degrees)

    dispatch = {
        ("yaw",   "left"):  view.YawLeft,
        ("yaw",   "right"): view.YawRight,
        ("pitch", "up"):    view.PitchUp,
        ("pitch", "down"):  view.PitchDown,
        ("roll",  "left"):  view.RollLeft,
        ("roll",  "right"): view.RollRight,
    }
    fn = dispatch.get((axis, direction))
    if fn is None:
        raise ValueError(f"Unknown axis/direction: {axis}/{direction}")
    fn()
    slicer.app.processEvents()


def rotate_animated(total_degrees=360, step_degrees=5, interval_ms=50,
                    axis="yaw", direction="left", widget_index=0,
                    on_complete=None):
    """
    Animate a rotation of `total_degrees` using a QTimer.

    total_degrees:  total rotation angle
    step_degrees:   degrees per timer tick
    interval_ms:    timer interval in milliseconds
    on_complete:    optional callable fired when rotation finishes
    """
    view = get_3d_view(widget_index)
    view.setPitchRollYawIncrement(step_degrees)

    dispatch = {
        ("yaw",   "left"):  view.YawLeft,
        ("yaw",   "right"): view.YawRight,
        ("pitch", "up"):    view.PitchUp,
        ("pitch", "down"):  view.PitchDown,
        ("roll",  "left"):  view.RollLeft,
        ("roll",  "right"): view.RollRight,
    }
    fn = dispatch[(axis, direction)]

    steps_total = int(total_degrees / step_degrees)
    state = {"steps_done": 0}

    timer = qt.QTimer()
    timer.setInterval(interval_ms)

    def _tick():
        if state["steps_done"] >= steps_total:
            timer.stop()
            if on_complete:
                on_complete()
            return
        fn()
        slicer.app.processEvents()
        state["steps_done"] += 1

    timer.timeout.connect(_tick)
    timer.start()
    return timer  # caller must keep a reference to prevent GC


def rotate_360_capture(output_dir, n_frames=4, step_degrees=5, interval_ms=40,
                       axis="yaw", direction="left", widget_index=0,
                       on_complete=None):
    """
    Rotate the 3D view 360° and capture `n_frames` evenly-spaced screenshots.

    output_dir:  directory to save frame_000.png, frame_001.png, …
    n_frames:    number of frames to capture (evenly spaced around 360°)
    on_complete: optional callable fired when done
    Returns the QTimer (keep reference alive).
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    view = get_3d_view(widget_index)
    view.setPitchRollYawIncrement(step_degrees)

    dispatch = {
        ("yaw",   "left"):  view.YawLeft,
        ("yaw",   "right"): view.YawRight,
        ("pitch", "up"):    view.PitchUp,
        ("pitch", "down"):  view.PitchDown,
        ("roll",  "left"):  view.RollLeft,
        ("roll",  "right"): view.RollRight,
    }
    fn = dispatch[(axis, direction)]

    steps_total = int(360 / step_degrees)
    capture_at = {int(i * steps_total / n_frames) for i in range(n_frames)}
    state = {"steps_done": 0, "frame": 0}

    timer = qt.QTimer()
    timer.setInterval(interval_ms)

    def _tick():
        if state["steps_done"] >= steps_total:
            timer.stop()
            if on_complete:
                on_complete()
            return

        fn()
        slicer.app.processEvents()

        if state["steps_done"] in capture_at:
            path = os.path.join(output_dir, f"frame_{state['frame']:03d}.png")
            pixmap = qt.QPixmap.grabWidget(slicer.util.mainWindow())
            pixmap.save(path)
            print(f"[rotate-3d-view] Saved {path}")
            state["frame"] += 1

        state["steps_done"] += 1

    timer.timeout.connect(_tick)
    timer.start()
    return timer


# ---------------------------------------------------------------------------
# Headless-safe helpers (verified on Xvfb)
# ---------------------------------------------------------------------------

def vtk_screenshot(render_window, path):
    """
    Save a render window to PNG using VTK's WindowToImageFilter.
    Works headless (Xvfb). Does NOT require a visible Qt window.

    render_window: vtkRenderWindow (e.g. view3d.renderWindow())
    path:          output .png path
    """
    import vtk
    wti = vtk.vtkWindowToImageFilter()
    wti.SetInput(render_window)
    wti.ReadFrontBufferOff()
    wti.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(path)
    writer.SetInputConnection(wti.GetOutputPort())
    writer.Write()


def rotate_to_standard_views(output_dir, on_complete=None, interval_ms=300,
                              widget_index=0):
    """
    Snap the 3D view to 4 standard orthogonal axes (Anterior, Left, Posterior, Right),
    capture a PNG at each position, then call on_complete.

    This is the RECOMMENDED approach for headless (Xvfb) screenshot sequences because
    rotateToViewAxis() triggers only ONE render per position (not 18 like YawLeft x18).

    Axes: 0=Left 1=Right 2=Posterior 3=Anterior 4=Inferior 5=Superior
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    AXES  = [3, 0, 2, 1]
    NAMES = ["anterior", "left", "posterior", "right"]
    state = {"stop": 0}

    def _step():
        stop = state["stop"]
        if stop >= len(AXES):
            if on_complete:
                on_complete()
            return

        view = get_3d_view(widget_index)
        view.rotateToViewAxis(AXES[stop])
        view.renderWindow().Render()

        path = os.path.join(output_dir, f"frame_{stop:02d}_{NAMES[stop]}.png")
        vtk_screenshot(view.renderWindow(), path)
        print(f"[rotate-3d-view] {NAMES[stop]} → {path}")

        state["stop"] += 1
        qt.QTimer.singleShot(interval_ms, _step)

    qt.QTimer.singleShot(0, _step)
