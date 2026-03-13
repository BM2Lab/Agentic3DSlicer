"""
SceneStateService — query the MRML scene and return a compact JSON snapshot.

Used by SlicerAgent at each step to give the LLM a current view of the scene.
"""
from __future__ import annotations
from .session import SlicerSession

# Code executed inside Slicer — returns a dict of scene node lists
_STATE_CODE = """
import slicer

def _node_info(node):
    return {"id": node.GetID(), "name": node.GetName(), "class": node.GetClassName()}

__result__ = {
    "volumes":      [_node_info(n) for n in slicer.util.getNodesByClass("vtkMRMLVolumeNode")],
    "segmentations":[_node_info(n) for n in slicer.util.getNodesByClass("vtkMRMLSegmentationNode")],
    "transforms":   [_node_info(n) for n in slicer.util.getNodesByClass("vtkMRMLTransformNode")],
    "markups":      [_node_info(n) for n in slicer.util.getNodesByClass("vtkMRMLMarkupsNode")],
    "total_nodes":  slicer.mrmlScene.GetNumberOfNodes(),
}
"""


class SceneStateService:
    def __init__(self, session: SlicerSession):
        self._session = session

    async def snapshot(self) -> dict:
        """
        Return a compact dict describing the current MRML scene:
            volumes, segmentations, transforms, markups, total_nodes
        """
        resp = await self._session.run_checked(_STATE_CODE)
        return resp["result"]

    async def summary(self) -> str:
        """Return a one-line human-readable scene summary for LLM context."""
        state = await self.snapshot()
        parts = []
        for key in ("volumes", "segmentations", "transforms", "markups"):
            nodes = state.get(key, [])
            if nodes:
                names = ", ".join(n["name"] for n in nodes)
                parts.append(f"{key}: [{names}]")
        if not parts:
            return "scene: empty"
        return "scene: " + " | ".join(parts)
