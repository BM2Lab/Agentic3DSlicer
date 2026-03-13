"""
Histogram and intensity analysis actions.

Actions:
    get_volume_histogram(node_id, bins, min_val, max_val)
        — compute voxel intensity histogram; returns {bins, counts, edges}
    get_intensity_at_point(node_id, ras)
        — sample volume intensity at a RAS coordinate
    compute_threshold_otsu(node_id)
        — compute Otsu threshold from volume histogram using numpy/scipy
    get_masked_stats(volume_id, seg_node_id, segment_name)
        — compute stats (min/max/mean/std) within a binary segment mask
"""
from __future__ import annotations
import json
from ..controller.service import controller
from ..slicer.session import SlicerSession

ns = controller.namespace("histogram", "Intensity histogram, point sampling, Otsu threshold, masked stats")


@ns.action(
    "Compute voxel intensity histogram for a scalar volume node"
)
async def get_volume_histogram(
    session: SlicerSession,
    node_id: str,
    bins: int = 256,
    min_val: float | None = None,
    max_val: float | None = None,
) -> dict:
    """
    Returns {bins, counts (list[int]), edges (list[float]), min, max}.
    If min_val/max_val are None the full scalar range is used.
    """
    min_arg = "None" if min_val is None else str(min_val)
    max_arg = "None" if max_val is None else str(max_val)
    resp = await session.run_checked(f"""
import slicer, numpy as np
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
arr = slicer.util.arrayFromVolume(node).flatten().astype(float)

vmin = float(arr.min()) if {min_arg} is None else {min_arg}
vmax = float(arr.max()) if {max_arg} is None else {max_arg}

counts, edges = np.histogram(arr, bins={bins}, range=(vmin, vmax))
__result__ = {{
    "bins":  {bins},
    "counts": counts.tolist(),
    "edges":  edges.tolist(),
    "min":    vmin,
    "max":    vmax,
}}
""")
    return resp["result"]


@ns.action(
    "Sample the scalar intensity of a volume at a single RAS coordinate"
)
async def get_intensity_at_point(
    session: SlicerSession,
    node_id: str,
    ras: list,
) -> float:
    """
    ras: [x, y, z] in RAS mm.
    Returns the interpolated scalar value at that point (float), or None if outside.
    """
    resp = await session.run_checked(f"""
import slicer, vtk
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
ras = {json.dumps(ras)}

rasToIjk = vtk.vtkMatrix4x4()
node.GetRASToIJKMatrix(rasToIjk)
ijk = [0.0, 0.0, 0.0, 1.0]
rasToIjk.MultiplyPoint(ras + [1.0], ijk)
i, j, k = int(round(ijk[0])), int(round(ijk[1])), int(round(ijk[2]))

imageData = node.GetImageData()
dims = imageData.GetDimensions()
if 0 <= i < dims[0] and 0 <= j < dims[1] and 0 <= k < dims[2]:
    val = imageData.GetScalarComponentAsDouble(i, j, k, 0)
else:
    val = None
__result__ = val
""")
    return resp["result"]


@ns.action(
    "Compute Otsu optimal threshold for a scalar volume using the histogram method"
)
async def compute_threshold_otsu(
    session: SlicerSession,
    node_id: str,
) -> dict:
    """
    Pure-numpy Otsu threshold (no scipy needed).
    Returns {threshold, below_mean, above_mean}.
    """
    resp = await session.run_checked(f"""
import slicer, numpy as np
node = slicer.mrmlScene.GetNodeByID({json.dumps(node_id)})
arr = slicer.util.arrayFromVolume(node).flatten().astype(float)

# Otsu's method via histogram
counts, bin_edges = np.histogram(arr, bins=256)
bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
total = counts.sum()
cumsum = np.cumsum(counts)
cumsum_val = np.cumsum(counts * bin_centers)
w1 = cumsum / total
w2 = 1.0 - w1
mu1 = np.where(w1 > 0, cumsum_val / np.maximum(cumsum, 1), 0)
mu2 = np.where(w2 > 0, (cumsum_val[-1] - cumsum_val) / np.maximum(total - cumsum, 1), 0)
variance = w1 * w2 * (mu1 - mu2) ** 2
best_idx = int(np.argmax(variance))
threshold = float(bin_centers[best_idx])

__result__ = {{
    "threshold":   threshold,
    "below_mean":  float(arr[arr <= threshold].mean()) if (arr <= threshold).any() else None,
    "above_mean":  float(arr[arr  > threshold].mean()) if (arr  > threshold).any() else None,
}}
""")
    return resp["result"]


@ns.action(
    "Compute intensity statistics (min/max/mean/std/voxel_count) within a named segment mask"
)
async def get_masked_stats(
    session: SlicerSession,
    volume_id: str,
    seg_node_id: str,
    segment_name: str,
) -> dict:
    """
    Returns {min, max, mean, std, voxel_count, segment_name}.
    Uses binary labelmap representation of the segment.
    """
    resp = await session.run_checked(f"""
import slicer, numpy as np

volNode = slicer.mrmlScene.GetNodeByID({json.dumps(volume_id)})
segNode = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
seg = segNode.GetSegmentation()
segId = seg.GetSegmentIdBySegmentName({json.dumps(segment_name)})
if not segId and seg.GetSegment({json.dumps(segment_name)}):
    segId = {json.dumps(segment_name)}
if not segId:
    raise RuntimeError(f"Segment {{repr({json.dumps(segment_name)})}} not found (by name or ID)")

# Export segment to labelmap in volume space
labelmapNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
    segNode, [segId], labelmapNode, volNode)

volArr  = slicer.util.arrayFromVolume(volNode)
maskArr = slicer.util.arrayFromVolume(labelmapNode).astype(bool)
slicer.mrmlScene.RemoveNode(labelmapNode)

masked = volArr[maskArr]
if masked.size == 0:
    __result__ = {{
        "segment_name": {json.dumps(segment_name)},
        "voxel_count": 0,
        "min": None, "max": None, "mean": None, "std": None,
    }}
else:
    __result__ = {{
        "segment_name": {json.dumps(segment_name)},
        "voxel_count":  int(masked.size),
        "min":          float(masked.min()),
        "max":          float(masked.max()),
        "mean":         float(masked.mean()),
        "std":          float(masked.std()),
    }}
""")
    return resp["result"]
