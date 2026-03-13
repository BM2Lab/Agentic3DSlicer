"""
Markup actions — from slicer.readthedocs.io markups script repository.

Actions:
    create_point_list(name)               — vtkMRMLMarkupsFiducialNode
    add_control_point(node_id, ras, label)— add a named RAS point
    get_control_points(node_id)           — list of {index, label, ras}
    clear_control_points(node_id)         — remove all points
    load_markups(path)                    — load .fcsv / .mkp.json
    save_markups(node_id, path)           — save to file
    create_roi(name, center, size)        — vtkMRMLMarkupsROINode (for crop volume)
"""
from __future__ import annotations
import json
from ..controller.service import controller
from ..slicer.session import SlicerSession

ns = controller.namespace("markup", "Fiducial points, ROIs, markup load/save")


@ns.action("Create an empty fiducial point list (vtkMRMLMarkupsFiducialNode)")
async def create_point_list(session: SlicerSession, name: str = "Points") -> dict:
    """Returns {id, name}."""
    resp = await session.run_checked(f"""
import slicer
node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", {json.dumps(name)})
node.CreateDefaultDisplayNodes()
__result__ = {{"id": node.GetID(), "name": node.GetName()}}
""")
    return resp["result"]


@ns.action("Add a control point (fiducial) to a markup node with a label")
async def add_control_point(
    session: SlicerSession,
    node_id: str,
    ras: list,
    label: str = "",
) -> int:
    """ras: [x, y, z] in RAS mm. Returns the 0-based index of the added point."""
    resp = await session.run_checked(f"""
import slicer
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
idx = node.AddControlPoint({json.dumps(ras)})
if {json.dumps(label)}:
    node.SetNthControlPointLabel(idx, {json.dumps(label)})
__result__ = idx
""")
    return resp["result"]


@ns.action("Get all control points from a markup node as a list of {index, label, ras}")
async def get_control_points(session: SlicerSession, node_id: str) -> list:
    """Returns list of {index, label, ras} dicts."""
    resp = await session.run_checked(f"""
import slicer
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
results = []
for i in range(node.GetNumberOfControlPoints()):
    ras = [0.0, 0.0, 0.0]
    node.GetNthControlPointPositionWorld(i, ras)
    results.append({{
        "index": i,
        "label": node.GetNthControlPointLabel(i),
        "ras":   list(ras),
    }})
__result__ = results
""")
    return resp["result"]


@ns.action("Remove all control points from a markup node")
async def clear_control_points(session: SlicerSession, node_id: str) -> int:
    """Returns the number of points that were removed."""
    resp = await session.run_checked(f"""
import slicer
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
n = node.GetNumberOfControlPoints()
node.RemoveAllControlPoints()
__result__ = n
""")
    return resp["result"]


@ns.action("Load a markups file (.fcsv or .mkp.json) into the scene")
async def load_markups(session: SlicerSession, path: str) -> dict:
    """Returns {id, name, num_points}."""
    resp = await session.run_checked(f"""
import slicer
node = slicer.util.loadMarkups({json.dumps(path)})
__result__ = {{
    "id":         node.GetID(),
    "name":       node.GetName(),
    "num_points": node.GetNumberOfControlPoints(),
}}
""")
    return resp["result"]


@ns.action("Save a markup node to a file (.fcsv or .mkp.json)")
async def save_markups(session: SlicerSession, node_id: str, path: str) -> str:
    """Returns the output path."""
    resp = await session.run_checked(f"""
import slicer
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
slicer.util.saveNode(node, {json.dumps(path)})
__result__ = {json.dumps(path)}
""")
    return resp["result"]


@ns.action("Create an ROI markup node (for use with crop volume)")
async def create_roi(
    session: SlicerSession,
    name: str = "ROI",
    center: list | None = None,
    size: list | None = None,
) -> dict:
    """
    center: [x, y, z] RAS mm. size: [sx, sy, sz] mm. Defaults to [0,0,0] and [50,50,50].
    Returns {id, name}.
    """
    c = center or [0.0, 0.0, 0.0]
    s = size or [50.0, 50.0, 50.0]
    resp = await session.run_checked(f"""
import slicer
roi = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsROINode", {json.dumps(name)})
roi.CreateDefaultDisplayNodes()
roi.SetCenter({json.dumps(c)})
roi.SetSize({json.dumps(s)})
__result__ = {{"id": roi.GetID(), "name": roi.GetName()}}
""")
    return resp["result"]
