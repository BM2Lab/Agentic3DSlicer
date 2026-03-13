"""
Crop Volume actions — wrapper around the CropVolume Slicer module.

Actions:
    crop_volume(volume_id, roi_id, interpolation, spacing_mode, isotropic_spacing)
        — crop a volume to an ROI; returns new volume {id, name}
    autocrop_volume(volume_id, margin_percent)
        — auto-fit an ROI to non-zero voxels and crop; returns {roi_id, volume_id, name}
"""
from __future__ import annotations
import json
from ..controller.service import controller
from ..slicer.session import SlicerSession

ns = controller.namespace("crop", "Volume cropping to ROI or auto-detected bounding box")


@ns.action(
    "Crop a volume node to a vtkMRMLMarkupsROINode bounding box; "
    "returns {id, name} of the output volume"
)
async def crop_volume(
    session: SlicerSession,
    volume_id: str,
    roi_id: str,
    interpolation: int = 1,
    spacing_mode: int = 0,
    isotropic_spacing: float = 1.0,
) -> dict:
    """
    interpolation: 0=NearestNeighbor, 1=Linear (default), 2=WindowedSinc, 3=BSpline
    spacing_mode:  0=minimum (preserve original), 1=voxel_size (isotropic_spacing mm/vox)
    Returns {id, name} of the cropped output volume.
    """
    resp = await session.run_checked(f"""
import slicer
volumeNode = slicer.mrmlScene.GetNodeByID({json.dumps(volume_id)})
roiNode    = slicer.mrmlScene.GetNodeByID({json.dumps(roi_id)})

params = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLCropVolumeParametersNode")
params.SetInputVolumeNodeID(volumeNode.GetID())
params.SetROINodeID(roiNode.GetID())
params.SetInterpolationMode({interpolation})
isotropic = {spacing_mode} == 1
params.SetIsotropicResampling(isotropic)
if isotropic:
    params.SetSpacingScalingConst({isotropic_spacing})

slicer.modules.cropvolume.logic().Apply(params)

out = slicer.mrmlScene.GetNodeByID(params.GetOutputVolumeNodeID())
slicer.mrmlScene.RemoveNode(params)
__result__ = {{"id": out.GetID(), "name": out.GetName()}}
""")
    return resp["result"]


@ns.action(
    "Auto-fit an ROI to the non-zero voxel bounding box of a volume and crop it; "
    "returns {roi_id, volume_id, name}"
)
async def autocrop_volume(
    session: SlicerSession,
    volume_id: str,
    margin_percent: float = 5.0,
) -> dict:
    """
    Creates a tight ROI around non-zero voxels (+ margin_percent padding),
    crops the volume, returns {roi_id, volume_id, name}.
    """
    resp = await session.run_checked(f"""
import slicer, numpy as np, vtk

volumeNode = slicer.mrmlScene.GetNodeByID({json.dumps(volume_id)})
arr = slicer.util.arrayFromVolume(volumeNode)

# Find bounding box of non-zero voxels (numpy Z,Y,X order)
nz = np.nonzero(arr)
if len(nz[0]) == 0:
    raise RuntimeError("Volume has no non-zero voxels")

zmin, zmax = int(nz[0].min()), int(nz[0].max())
ymin, ymax = int(nz[1].min()), int(nz[1].max())
xmin, xmax = int(nz[2].min()), int(nz[2].max())

# Add margin
margin = {margin_percent} / 100.0
dz = max(1, int((zmax - zmin) * margin))
dy = max(1, int((ymax - ymin) * margin))
dx = max(1, int((xmax - xmin) * margin))
shape = arr.shape  # Z, Y, X

zmin = max(0, zmin - dz); zmax = min(shape[0]-1, zmax + dz)
ymin = max(0, ymin - dy); ymax = min(shape[1]-1, ymax + dy)
xmin = max(0, xmin - dx); xmax = min(shape[2]-1, xmax + dx)

# Convert voxel indices to RAS
_m = vtk.vtkMatrix4x4()
volumeNode.GetIJKToRASMatrix(_m)
ijkToRas = slicer.util.arrayFromVTKMatrix(_m)

def vox_to_ras(i, j, k):
    v = ijkToRas @ np.array([i, j, k, 1.0])
    return v[:3].tolist()

corners_ras = [
    vox_to_ras(xmin, ymin, zmin),
    vox_to_ras(xmax, ymax, zmax),
]
center = [(a+b)/2 for a, b in zip(corners_ras[0], corners_ras[1])]
size   = [abs(b-a) for a, b in zip(corners_ras[0], corners_ras[1])]

roi = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsROINode",
                                          volumeNode.GetName() + "_AutoROI")
roi.CreateDefaultDisplayNodes()
roi.SetCenter(center)
roi.SetSize(size)

params = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLCropVolumeParametersNode")
params.SetInputVolumeNodeID(volumeNode.GetID())
params.SetROINodeID(roi.GetID())
params.SetInterpolationMode(1)
params.SetIsotropicResampling(False)
slicer.modules.cropvolume.logic().Apply(params)

out = slicer.mrmlScene.GetNodeByID(params.GetOutputVolumeNodeID())
slicer.mrmlScene.RemoveNode(params)

__result__ = {{
    "roi_id":    roi.GetID(),
    "volume_id": out.GetID(),
    "name":      out.GetName(),
}}
""")
    return resp["result"]
