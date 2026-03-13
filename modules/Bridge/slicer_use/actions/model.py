"""
Model actions — from slicer.readthedocs.io models script repository.

Actions:
    load_model(path)                     — load STL/OBJ/VTP/PLY model
    get_model_stats(node_id)             — surface area mm2, volume mm3 via vtkMassProperties
    export_model(node_id, path)          — save to STL/OBJ/etc.
    segmentation_to_models(seg_id)       — export all segments as model nodes
    set_model_display(node_id, color, opacity) — set colour and opacity
"""
from __future__ import annotations
import json
from ..controller.service import controller
from ..slicer.session import SlicerSession

ns = controller.namespace("model", "3D surface models: load, export, stats, display")


@ns.action("Load a 3D surface model file (STL, OBJ, VTP, PLY) into the scene")
async def load_model(session: SlicerSession, path: str) -> dict:
    """Returns {id, name}."""
    resp = await session.run_checked(f"""
import slicer
node = slicer.util.loadModel({json.dumps(path)})
__result__ = {{"id": node.GetID(), "name": node.GetName()}}
""")
    return resp["result"]


@ns.action("Compute surface area (mm2) and volume (mm3) of a model node using vtkMassProperties")
async def get_model_stats(session: SlicerSession, node_id: str) -> dict:
    """
    Triangulates the mesh first (required by vtkMassProperties).
    Returns {surface_area_mm2, volume_mm3, num_points, num_cells}.
    Note: volume_mm3 is only valid for closed (watertight) meshes.
    """
    resp = await session.run_checked(f"""
import slicer, vtk
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
mesh = node.GetMesh()

tri = vtk.vtkTriangleFilter()
tri.SetInputDataObject(mesh)
tri.Update()

mass = vtk.vtkMassProperties()
mass.SetInputData(tri.GetOutput())
mass.Update()

__result__ = {{
    "surface_area_mm2": mass.GetSurfaceArea(),
    "volume_mm3":       mass.GetVolume(),
    "num_points":       mesh.GetNumberOfPoints(),
    "num_cells":        mesh.GetNumberOfCells(),
}}
""")
    return resp["result"]


@ns.action("Export a model node to a file (STL, OBJ, VTP, PLY)")
async def export_model(session: SlicerSession, node_id: str, path: str) -> str:
    """Returns the output path."""
    resp = await session.run_checked(f"""
import slicer
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
slicer.util.exportNode(node, {json.dumps(path)})
__result__ = {json.dumps(path)}
""")
    return resp["result"]


@ns.action("Convert all segments of a segmentation to individual model nodes")
async def segmentation_to_models(session: SlicerSession, seg_node_id: str) -> list:
    """
    Uses ExportAllSegmentsToModels. Returns list of {id, name} for each created model node.
    """
    resp = await session.run_checked(f"""
import slicer
seg = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
seg.CreateClosedSurfaceRepresentation()

shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
folderId = shNode.CreateFolderItem(shNode.GetSceneItemID(), seg.GetName() + "_Models")
slicer.modules.segmentations.logic().ExportAllSegmentsToModels(seg, folderId)

# Collect the model nodes created under the folder
childIds = vtk.vtkIdList()
shNode.GetItemChildren(folderId, childIds, True)
models = []
for i in range(childIds.GetNumberOfIds()):
    item = childIds.GetId(i)
    node = shNode.GetItemDataNode(item)
    if node and node.IsA("vtkMRMLModelNode"):
        models.append({{"id": node.GetID(), "name": node.GetName()}})
__result__ = models
""")
    return resp["result"]


@ns.action("Set the display colour and opacity of a model node")
async def set_model_display(
    session: SlicerSession,
    node_id: str,
    color: list | None = None,
    opacity: float = 1.0,
) -> str:
    """color: [r, g, b] floats 0–1. Returns node_id."""
    c = color or [1.0, 0.0, 0.0]
    resp = await session.run_checked(f"""
import slicer
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
dn = node.GetDisplayNode()
dn.SetColor({c[0]}, {c[1]}, {c[2]})
dn.SetOpacity({opacity})
__result__ = {json.dumps(node_id)}
""")
    return resp["result"]
