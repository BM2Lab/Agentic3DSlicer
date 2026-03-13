"""
Visualization actions — migrated from tools/visualization/

Registered actions:
    set_layout(layout)                          — switch Slicer layout
    capture_screenshot(output_path)             — save 3D view as PNG
    enable_volume_rendering(node_id, preset)    — enable VR with named preset
    rotate_3d_view(axis, direction, degrees)    — single rotation step
"""
from __future__ import annotations
import json
from ..controller.service import controller
from ..slicer.session import SlicerSession

ns = controller.namespace("visualization", "Layout, screenshots, volume rendering, camera rotation")

# Valid layout names and their Slicer constants
LAYOUTS = {
    "four_up":    "slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView",
    "3d_only":    "slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView",
    "red_only":   "slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView",
}


@ns.action("Switch the Slicer layout (four_up | 3d_only | red_only)")
async def set_layout(session: SlicerSession, layout: str = "four_up") -> str:
    const = LAYOUTS.get(layout)
    if const is None:
        raise ValueError(f"Unknown layout {layout!r}. Valid: {list(LAYOUTS)}")
    resp = await session.run_checked(f"""
import slicer
slicer.app.layoutManager().setLayout({const})
slicer.app.processEvents()
__result__ = "layout set: {layout}"
""")
    return resp["result"]


@ns.action("Capture the 3D view as a PNG screenshot")
async def capture_screenshot(session: SlicerSession, output_path: str) -> str:
    """
    Migrated from: tools/visualization/capture-3d-screenshot.py
    Uses VTK WindowToImageFilter (works headless on Xvfb).
    Returns output_path on success.
    """
    code = f"""
import slicer, vtk
lm = slicer.app.layoutManager()
if lm is None or lm.threeDWidget(0) is None:
    raise RuntimeError("capture_screenshot requires GUI mode (no --no-main-window). "
                       "threeDWidget is None in headless mode.")
view3d = lm.threeDWidget(0).threeDView()
view3d.renderWindow().Render()
wti = vtk.vtkWindowToImageFilter()
wti.SetInput(view3d.renderWindow())
wti.ReadFrontBufferOff()
wti.Update()
writer = vtk.vtkPNGWriter()
writer.SetFileName({json.dumps(output_path)})
writer.SetInputConnection(wti.GetOutputPort())
writer.Write()
__result__ = {json.dumps(output_path)}
"""
    resp = await session.run_checked(code)
    return resp["result"]


@ns.action("Enable volume rendering on a volume node with a named preset")
async def enable_volume_rendering(
    session: SlicerSession,
    node_id: str,
    preset: str = "CT-Bone",
) -> str:
    """
    Migrated from: tools/visualization/enable-volume-rendering.py
    preset: MR-Default | CT-Bone | CT-Chest | MR-MIP | CT-AAA
    Returns node_id on success.
    """
    code = f"""
import slicer
volNode = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
volRenLogic = slicer.modules.volumerendering.logic()
displayNode = volRenLogic.CreateVolumeRenderingDisplayNode()
slicer.mrmlScene.AddNode(displayNode)
displayNode.UnRegister(volRenLogic)
volRenLogic.UpdateDisplayNodeFromVolumeNode(displayNode, volNode)
volNode.AddAndObserveDisplayNodeID(displayNode.GetID())
presetNode = volRenLogic.GetPresetByName({json.dumps(preset)})
if presetNode:
    displayNode.GetVolumePropertyNode().Copy(presetNode)
displayNode.SetVisibility(True)
slicer.app.processEvents()
__result__ = {json.dumps(node_id)}
"""
    resp = await session.run_checked(code)
    return resp["result"]


@ns.action("Rotate the 3D view by a given angle (uses VTK camera — works live)")
async def rotate_3d_view(
    session: SlicerSession,
    axis: str = "azimuth",
    degrees: float = 90.0,
) -> str:
    """
    Migrated from: tools/visualization/rotate-3d-view.py
    axis: 'azimuth' (yaw) | 'elevation' (pitch)
    Uses camera.Azimuth()/Elevation() — the only method that works on live displays.
    """
    if axis not in ("azimuth", "elevation"):
        raise ValueError("axis must be 'azimuth' or 'elevation'")
    code = f"""
import slicer
view3d = slicer.app.layoutManager().threeDWidget(0).threeDView()
rw = view3d.renderWindow()
renderer = rw.GetRenderers().GetFirstRenderer()
camera = renderer.GetActiveCamera()
camera.{axis.capitalize()}({degrees})
renderer.ResetCameraClippingRange()
rw.Render()
__result__ = "rotated {degrees}deg {axis}"
"""
    resp = await session.run_checked(code)
    return resp["result"]
