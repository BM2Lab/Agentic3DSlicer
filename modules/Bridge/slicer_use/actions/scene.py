"""
Scene actions — migrated from tools/scene/list-mrml-nodes.py

Registered actions:
    list_nodes()        — all MRML nodes in the scene
    get_scene_state()   — structured snapshot (volumes, segs, transforms, markups)
"""
from __future__ import annotations
from ..controller.service import controller
from ..slicer.session import SlicerSession

ns = controller.namespace("scene", "MRML scene inspection and snapshots")


@ns.action("List all MRML nodes in the current scene")
async def list_nodes(session: SlicerSession) -> list[dict]:
    """
    Migrated from: tools/scene/list-mrml-nodes.py
    Returns a list of {index, id, name, class} for every node in the scene.
    """
    resp = await session.run_checked("""
import slicer
nodes = []
for i in range(slicer.mrmlScene.GetNumberOfNodes()):
    n = slicer.mrmlScene.GetNthNode(i)
    nodes.append({"index": i, "id": n.GetID(), "name": n.GetName(), "class": n.GetClassName()})
__result__ = nodes
""")
    return resp["result"]


@ns.action("Get a compact JSON snapshot of the current MRML scene")
async def get_scene_state(session: SlicerSession) -> dict:
    """
    Returns dict with keys: volumes, segmentations, transforms, markups, total_nodes.
    Each entry is a list of {id, name, class} dicts.
    """
    resp = await session.run_checked("""
import slicer

def _info(n):
    return {"id": n.GetID(), "name": n.GetName(), "class": n.GetClassName()}

__result__ = {
    "volumes":       [_info(n) for n in slicer.util.getNodesByClass("vtkMRMLVolumeNode")],
    "segmentations": [_info(n) for n in slicer.util.getNodesByClass("vtkMRMLSegmentationNode")],
    "transforms":    [_info(n) for n in slicer.util.getNodesByClass("vtkMRMLTransformNode")],
    "markups":       [_info(n) for n in slicer.util.getNodesByClass("vtkMRMLMarkupsNode")],
    "total_nodes":   slicer.mrmlScene.GetNumberOfNodes(),
}
""")
    return resp["result"]
