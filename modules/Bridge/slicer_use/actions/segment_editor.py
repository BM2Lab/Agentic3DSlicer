"""
Segment Editor actions — headless-safe numpy/scipy implementations.

Uses binary labelmap arrays + scipy morphology instead of qMRMLSegmentEditorWidget
(which crashes Slicer in --no-main-window mode).

Actions:
    islands_keep_largest(seg_node_id, segment_name)
        — keep only the largest connected island in a binary segment
    smooth_segment(seg_node_id, segment_name, method, kernel_size)
        — smooth a segment with Median/Gaussian/Opening/Closing
    threshold_auto(seg_node_id, segment_name, volume_id, method)
        — auto-threshold using Otsu or percentile
    margin_segment(seg_node_id, segment_name, margin_mm)
        — grow (+) or shrink (-) a segment by margin_mm
    hollow_segment(seg_node_id, segment_name, shell_thickness_mm)
        — hollow a segment to a shell of given thickness
"""
from __future__ import annotations
import json
from ..controller.service import controller
from ..slicer.session import SlicerSession

ns = controller.namespace("segment_editor", "Headless-safe segment editing: islands, smooth, threshold, margin, hollow")

# Helper: shared code to look up a segment by name OR ID
_FIND_SEG = """
_seg_obj = segNode.GetSegmentation()
_segId = _seg_obj.GetSegmentIdBySegmentName(_segment_name)
if not _segId and _seg_obj.GetSegment(_segment_name):
    _segId = _segment_name
if not _segId:
    raise RuntimeError(f"Segment {repr(_segment_name)!r} not found (by name or ID)")
"""


@ns.action(
    "Keep only the largest connected island in a binary segment (removes small fragments)"
)
async def islands_keep_largest(
    session: SlicerSession,
    seg_node_id: str,
    segment_name: str,
) -> dict:
    """
    Uses scipy.ndimage.label for connected components.
    Returns {segment_name, islands_removed, voxel_count}.
    """
    resp = await session.run_checked(f"""
import slicer, numpy as np
from scipy import ndimage

segNode = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
_segment_name = {json.dumps(segment_name)}
_seg_obj = segNode.GetSegmentation()
_segId = _seg_obj.GetSegmentIdBySegmentName(_segment_name)
if not _segId and _seg_obj.GetSegment(_segment_name):
    _segId = _segment_name
if not _segId:
    raise RuntimeError(f"Segment {{repr(_segment_name)}} not found")

# Get reference volume for geometry
ref_ids = [segNode.GetNodeReferenceID("referenceImageGeometryRef")]
ref_vol = None
if ref_ids[0]:
    ref_vol = slicer.mrmlScene.GetNodeByID(ref_ids[0])

arr = slicer.util.arrayFromSegmentBinaryLabelmap(segNode, _segId, ref_vol)
arr = arr.astype(np.uint8)

labeled, n_components = ndimage.label(arr)
if n_components <= 1:
    __result__ = {{"segment_name": _segment_name, "islands_removed": 0,
                   "voxel_count": int(arr.sum())}}
else:
    # Find the largest component
    sizes = ndimage.sum(arr, labeled, range(1, n_components + 1))
    largest_label = int(np.argmax(sizes)) + 1
    result = (labeled == largest_label).astype(np.uint8)
    slicer.util.updateSegmentBinaryLabelmapFromArray(result, segNode, _segId, ref_vol)
    __result__ = {{
        "segment_name":    _segment_name,
        "islands_removed": n_components - 1,
        "voxel_count":     int(result.sum()),
    }}
""")
    return resp["result"]


@ns.action(
    "Smooth a segment using numpy/scipy morphology (headless-safe)"
)
async def smooth_segment(
    session: SlicerSession,
    seg_node_id: str,
    segment_name: str,
    method: str = "MEDIAN",
    kernel_size: int = 3,
) -> dict:
    """
    method: MEDIAN (default), GAUSSIAN, OPENING (erosion+dilation), CLOSING (dilation+erosion).
    kernel_size: integer kernel size in voxels (3 = 3×3×3).
    Returns {segment_name, voxel_count}.
    """
    resp = await session.run_checked(f"""
import slicer, numpy as np
from scipy import ndimage

segNode = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
_segment_name = {json.dumps(segment_name)}
_seg_obj = segNode.GetSegmentation()
_segId = _seg_obj.GetSegmentIdBySegmentName(_segment_name)
if not _segId and _seg_obj.GetSegment(_segment_name):
    _segId = _segment_name
if not _segId:
    raise RuntimeError(f"Segment {{repr(_segment_name)}} not found")

ref_ids = [segNode.GetNodeReferenceID("referenceImageGeometryRef")]
ref_vol = None
if ref_ids[0]:
    ref_vol = slicer.mrmlScene.GetNodeByID(ref_ids[0])

arr = slicer.util.arrayFromSegmentBinaryLabelmap(segNode, _segId, ref_vol).astype(np.uint8)
method = {json.dumps(method)}
ks = {kernel_size}
struct = ndimage.generate_binary_structure(3, 1)

if method == "MEDIAN":
    result = ndimage.median_filter(arr, size=ks)
elif method == "GAUSSIAN":
    blurred = ndimage.gaussian_filter(arr.astype(float), sigma=ks/3.0)
    result = (blurred > 0.5).astype(np.uint8)
elif method == "OPENING":
    eroded = ndimage.binary_erosion(arr, iterations=ks//2)
    result = ndimage.binary_dilation(eroded, iterations=ks//2).astype(np.uint8)
elif method == "CLOSING":
    dilated = ndimage.binary_dilation(arr, iterations=ks//2)
    result = ndimage.binary_erosion(dilated, iterations=ks//2).astype(np.uint8)
else:
    raise ValueError(f"Unknown smoothing method: {{method!r}}")

slicer.util.updateSegmentBinaryLabelmapFromArray(result, segNode, _segId, ref_vol)
__result__ = {{"segment_name": _segment_name, "voxel_count": int(result.sum())}}
""")
    return resp["result"]


@ns.action(
    "Auto-threshold a volume into a segment using Otsu or percentile method"
)
async def threshold_auto(
    session: SlicerSession,
    seg_node_id: str,
    segment_name: str,
    volume_id: str,
    method: str = "OTSU",
    lower_percentile: float = 10.0,
    upper_percentile: float = 100.0,
) -> dict:
    """
    method: OTSU (default) or PERCENTILE.
    For PERCENTILE: lower_percentile..upper_percentile of non-zero voxels.
    Creates the segment if it doesn't exist.
    Returns {segment_name, threshold_min, threshold_max, voxel_count}.
    """
    resp = await session.run_checked(f"""
import slicer, numpy as np

segNode = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
volNode = slicer.mrmlScene.GetNodeByID({json.dumps(volume_id)})
_segment_name = {json.dumps(segment_name)}
_seg_obj = segNode.GetSegmentation()
_segId = _seg_obj.GetSegmentIdBySegmentName(_segment_name)
if not _segId and _seg_obj.GetSegment(_segment_name):
    _segId = _segment_name
if not _segId:
    _segId = _seg_obj.AddEmptySegment(_segment_name)
    _seg_obj.GetSegment(_segId).SetName(_segment_name)

vol_arr = slicer.util.arrayFromVolume(volNode).flatten().astype(float)
method = {json.dumps(method)}

if method == "OTSU":
    counts, bin_edges = np.histogram(vol_arr, bins=256)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    total = counts.sum()
    cumsum = np.cumsum(counts)
    cumsum_val = np.cumsum(counts * bin_centers)
    w1 = cumsum / total
    w2 = 1.0 - w1
    mu1 = np.where(w1 > 0, cumsum_val / np.maximum(cumsum, 1), 0)
    mu2_num = cumsum_val[-1] - cumsum_val
    mu2 = np.where(w2 > 0, mu2_num / np.maximum(total - cumsum, 1), 0)
    variance = w1 * w2 * (mu1 - mu2) ** 2
    thr = float(bin_centers[np.argmax(variance)])
    thr_min, thr_max = thr, float(vol_arr.max())
elif method == "PERCENTILE":
    nz = vol_arr[vol_arr > 0] if (vol_arr > 0).any() else vol_arr
    thr_min = float(np.percentile(nz, {lower_percentile}))
    thr_max = float(np.percentile(nz, {upper_percentile}))
else:
    raise ValueError(f"Unknown method {{method!r}}")

# Apply threshold to full 3D array (use zeros_like to avoid empty-segment export failure)
full_arr = slicer.util.arrayFromVolume(volNode)
seg_arr = np.zeros(full_arr.shape, dtype=np.uint8)
seg_arr[(full_arr >= thr_min) & (full_arr <= thr_max)] = 1
slicer.util.updateSegmentBinaryLabelmapFromArray(seg_arr, segNode, _segId, volNode)

__result__ = {{
    "segment_name":  _segment_name,
    "threshold_min": thr_min,
    "threshold_max": thr_max,
    "voxel_count":   int(seg_arr.sum()),
}}
""")
    return resp["result"]


@ns.action(
    "Grow (+) or shrink (-) a segment by a margin in mm using morphological dilation/erosion"
)
async def margin_segment(
    session: SlicerSession,
    seg_node_id: str,
    segment_name: str,
    margin_mm: float = 3.0,
) -> dict:
    """
    margin_mm > 0 grows (dilation), < 0 shrinks (erosion).
    Iterations calculated from margin_mm / mean_voxel_spacing.
    Returns {segment_name, voxel_count, iterations_used}.
    """
    resp = await session.run_checked(f"""
import slicer, numpy as np
from scipy import ndimage

segNode = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
_segment_name = {json.dumps(segment_name)}
_seg_obj = segNode.GetSegmentation()
_segId = _seg_obj.GetSegmentIdBySegmentName(_segment_name)
if not _segId and _seg_obj.GetSegment(_segment_name):
    _segId = _segment_name
if not _segId:
    raise RuntimeError(f"Segment {{repr(_segment_name)}} not found")

ref_ids = [segNode.GetNodeReferenceID("referenceImageGeometryRef")]
ref_vol = None
if ref_ids[0]:
    ref_vol = slicer.mrmlScene.GetNodeByID(ref_ids[0])

arr = slicer.util.arrayFromSegmentBinaryLabelmap(segNode, _segId, ref_vol).astype(np.uint8)
margin_mm = {margin_mm}

# Estimate spacing from segmentation geometry string
spacing = [1.0, 1.0, 1.0]
if ref_vol:
    spacing = list(ref_vol.GetSpacing())
mean_spacing = float(np.mean(spacing))
iterations = max(1, int(round(abs(margin_mm) / mean_spacing)))

if margin_mm > 0:
    result = ndimage.binary_dilation(arr, iterations=iterations).astype(np.uint8)
else:
    result = ndimage.binary_erosion(arr, iterations=iterations).astype(np.uint8)

slicer.util.updateSegmentBinaryLabelmapFromArray(result, segNode, _segId, ref_vol)
__result__ = {{
    "segment_name":    _segment_name,
    "voxel_count":     int(result.sum()),
    "iterations_used": iterations,
}}
""")
    return resp["result"]


@ns.action(
    "Hollow a solid segment to a thin shell by subtracting an eroded copy"
)
async def hollow_segment(
    session: SlicerSession,
    seg_node_id: str,
    segment_name: str,
    shell_thickness_mm: float = 3.0,
) -> dict:
    """
    Creates a shell by eroding the segment and subtracting from original.
    Returns {segment_name, voxel_count}.
    """
    resp = await session.run_checked(f"""
import slicer, numpy as np
from scipy import ndimage

segNode = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
_segment_name = {json.dumps(segment_name)}
_seg_obj = segNode.GetSegmentation()
_segId = _seg_obj.GetSegmentIdBySegmentName(_segment_name)
if not _segId and _seg_obj.GetSegment(_segment_name):
    _segId = _segment_name
if not _segId:
    raise RuntimeError(f"Segment {{repr(_segment_name)}} not found")

ref_ids = [segNode.GetNodeReferenceID("referenceImageGeometryRef")]
ref_vol = None
if ref_ids[0]:
    ref_vol = slicer.mrmlScene.GetNodeByID(ref_ids[0])

arr = slicer.util.arrayFromSegmentBinaryLabelmap(segNode, _segId, ref_vol).astype(np.uint8)
spacing = list(ref_vol.GetSpacing()) if ref_vol else [1.0, 1.0, 1.0]
mean_spacing = float(np.mean(spacing))
iterations = max(1, int(round({shell_thickness_mm} / mean_spacing)))

interior = ndimage.binary_erosion(arr, iterations=iterations).astype(np.uint8)
shell = arr - interior

slicer.util.updateSegmentBinaryLabelmapFromArray(shell, segNode, _segId, ref_vol)
__result__ = {{"segment_name": _segment_name, "voxel_count": int(shell.sum())}}
""")
    return resp["result"]
