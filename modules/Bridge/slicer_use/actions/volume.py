"""
Volume actions — from tools/volumes/ and slicer.readthedocs.io script repository.

Actions:
    load_volume(path)               — load any supported volume file
    load_sample_mrhead()            — MRHead from SampleData
    load_sample_ct_abdomen()        — CTAAbdomenPanoramix from SampleData
    get_volume_info(node_id)        — spacing, origin, dims, scalar type
    get_volume_stats(node_id)       — min, max, mean, std via numpy
    clone_volume(node_id, name)     — deep-copy a volume node
    export_volume(node_id, path)    — save to NIfTI / NRRD / any supported format
    resample_volume(node_id, ref_id, interpolation)  — resample to reference geometry
"""
from __future__ import annotations
import json
from ..controller.service import controller
from ..slicer.session import SlicerSession

ns = controller.namespace("volume", "Volume loading, resampling, conversion, export")


@ns.action("Load a volume file into the scene (NIfTI, NRRD, DICOM dir, etc.)")
async def load_volume(session: SlicerSession, path: str) -> dict:
    """Returns {id, name} of the loaded vtkMRMLVolumeNode."""
    resp = await session.run_checked(f"""
import slicer
node = slicer.util.loadVolume({json.dumps(path)})
__result__ = {{"id": node.GetID(), "name": node.GetName()}}
""")
    return resp["result"]


@ns.action("Download and load the MRHead sample MRI volume")
async def load_sample_mrhead(session: SlicerSession) -> dict:
    """Returns {id, name}."""
    resp = await session.run_checked("""
import SampleData
node = SampleData.downloadSample("MRHead")
__result__ = {"id": node.GetID(), "name": node.GetName()}
""")
    return resp["result"]


@ns.action("Download and load the CTAAbdomenPanoramix sample CT volume")
async def load_sample_ct_abdomen(session: SlicerSession) -> dict:
    """Returns {id, name}."""
    resp = await session.run_checked("""
import SampleData
node = SampleData.downloadSample("CTAAbdomenPanoramix")
__result__ = {"id": node.GetID(), "name": node.GetName()}
""")
    return resp["result"]


@ns.action("Get metadata for a volume: spacing, origin, dimensions, scalar type")
async def get_volume_info(session: SlicerSession, node_id: str) -> dict:
    """Returns {id, name, spacing, origin, dimensions, scalar_type, scalar_range}."""
    resp = await session.run_checked(f"""
import slicer
n = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
img = n.GetImageData()
sr = img.GetScalarRange()
__result__ = {{
    "id":           n.GetID(),
    "name":         n.GetName(),
    "spacing":      list(n.GetSpacing()),
    "origin":       list(n.GetOrigin()),
    "dimensions":   list(img.GetDimensions()),
    "scalar_type":  img.GetScalarTypeAsString(),
    "scalar_range": [sr[0], sr[1]],
}}
""")
    return resp["result"]


@ns.action("Compute voxel statistics for a volume: min, max, mean, std, shape")
async def get_volume_stats(session: SlicerSession, node_id: str) -> dict:
    """
    Uses slicer.util.arrayFromVolume (numpy). Returns {min, max, mean, std, shape}.
    shape is [slices, rows, cols] (k, j, i ordering).
    """
    resp = await session.run_checked(f"""
import slicer, numpy as np
n = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
arr = slicer.util.arrayFromVolume(n)
__result__ = {{
    "min":   float(arr.min()),
    "max":   float(arr.max()),
    "mean":  float(arr.mean()),
    "std":   float(arr.std()),
    "shape": list(arr.shape),
}}
""")
    return resp["result"]


@ns.action("Clone a volume node (deep copy) with a new name")
async def clone_volume(session: SlicerSession, node_id: str, name: str = "Clone") -> dict:
    """Returns {id, name} of the cloned node."""
    resp = await session.run_checked(f"""
import slicer
src = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
cloned = slicer.modules.volumes.logic().CloneVolume(slicer.mrmlScene, src, {json.dumps(name)})
__result__ = {{"id": cloned.GetID(), "name": cloned.GetName()}}
""")
    return resp["result"]


@ns.action("Export a volume node to a file (NIfTI .nii.gz, NRRD, etc.)")
async def export_volume(session: SlicerSession, node_id: str, path: str) -> str:
    """Does NOT modify the node's storage path. Returns the output path."""
    resp = await session.run_checked(f"""
import slicer
n = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
slicer.util.exportNode(n, {json.dumps(path)})
__result__ = {json.dumps(path)}
""")
    return resp["result"]


@ns.action("Resample a volume to match the geometry of a reference volume")
async def resample_volume(
    session: SlicerSession,
    node_id: str,
    reference_id: str,
    interpolation: str = "linear",
    output_name: str = "Resampled",
) -> dict:
    """
    Uses the ResampleScalarVectorDWIVolume CLI module.
    interpolation: 'linear' | 'nn' (nearest-neighbor, for label maps) | 'bs' (b-spline)
    Returns {id, name} of the output node.
    """
    resp = await session.run_checked(f"""
import slicer
out = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", {json.dumps(output_name)})
params = {{
    "inputVolume":       {json.dumps(node_id)},
    "outputVolume":      out.GetID(),
    "referenceVolume":   {json.dumps(reference_id)},
    "interpolationType": {json.dumps(interpolation)},
}}
slicer.cli.runSync(slicer.modules.resamplescalarvectordwivolume, None, params)
__result__ = {{"id": out.GetID(), "name": out.GetName()}}
""")
    return resp["result"]
