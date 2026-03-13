"""
Transform actions — from slicer.readthedocs.io transforms script repository.

Actions:
    create_transform(name, matrix_4x4)    — create linear transform from 4×4 list
    apply_transform(node_id, tx_id)       — set node's parent transform
    harden_transform(node_id)             — bake transform into node data
    get_transform_matrix(tx_id)           — read the 4×4 matrix (to-world)
    load_transform(path)                  — load from .tfm / .h5 file
"""
from __future__ import annotations
import json
from ..controller.service import controller
from ..slicer.session import SlicerSession

ns = controller.namespace("transform", "Linear transforms: create, apply, harden, read, load")

_IDENTITY = [
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1],
]


@ns.action("Create a linear transform node from a 4×4 row-major matrix (list of 4 lists)")
async def create_transform(
    session: SlicerSession,
    name: str = "Transform",
    matrix_4x4: list | None = None,
) -> dict:
    """
    matrix_4x4: [[r00,r01,r02,t0],[r10,...], ...] in RAS space.
    Defaults to identity. Returns {id, name}.
    """
    mat = matrix_4x4 or _IDENTITY
    resp = await session.run_checked(f"""
import slicer
import numpy as np
tx = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", {json.dumps(name)})
mat = {json.dumps(mat)}
vtkMat = slicer.util.vtkMatrixFromArray(np.array(mat, dtype=float))
tx.SetMatrixTransformToParent(vtkMat)
__result__ = {{"id": tx.GetID(), "name": tx.GetName()}}
""")
    return resp["result"]


@ns.action("Apply a transform node to a scene node (set parent transform)")
async def apply_transform(
    session: SlicerSession,
    node_id: str,
    transform_id: str,
) -> str:
    """Sets node's parent transform. Returns node_id."""
    resp = await session.run_checked(f"""
import slicer
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
node.SetAndObserveTransformNodeID({json.dumps(transform_id)})
__result__ = {json.dumps(node_id)}
""")
    return resp["result"]


@ns.action("Harden (bake) a node's parent transform into its data, then clear the transform")
async def harden_transform(session: SlicerSession, node_id: str) -> str:
    """Returns node_id."""
    resp = await session.run_checked(f"""
import slicer
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
node.HardenTransform()
__result__ = {json.dumps(node_id)}
""")
    return resp["result"]


@ns.action("Read the 4×4 to-world matrix of a transform node")
async def get_transform_matrix(session: SlicerSession, transform_id: str) -> list:
    """Returns a 4×4 row-major list of lists."""
    resp = await session.run_checked(f"""
import slicer, vtk
tx = slicer.mrmlScene.GetNodeByID({json.dumps(transform_id)})
m = vtk.vtkMatrix4x4()
tx.GetMatrixTransformToWorld(m)
mat = []
for r in range(4):
    row = []
    for c in range(4):
        row.append(m.GetElement(r, c))
    mat.append(row)
__result__ = mat
""")
    return resp["result"]


@ns.action("Load a transform from a file (.tfm, .h5, .txt)")
async def load_transform(session: SlicerSession, path: str) -> dict:
    """Returns {id, name}."""
    resp = await session.run_checked(f"""
import slicer
tx = slicer.util.loadTransform({json.dumps(path)})
__result__ = {{"id": tx.GetID(), "name": tx.GetName()}}
""")
    return resp["result"]
