"""
Segmentation actions — from slicer.readthedocs.io segmentations script repository.

Actions:
    create_segmentation(name, ref_volume_id)       — empty segmentation node
    add_segment(seg_id, name, color)               — add a named segment
    threshold_segment(seg_id, seg_name, vol_id, lo, hi) — numpy-based threshold (headless safe)
    get_segment_stats(seg_id, vol_id)              — volume mm3, surface area, centroid per segment
    export_segmentation_nifti(seg_id, path)        — labelmap → NIfTI
    export_segmentation_stl(seg_id, output_dir)    — closed surface → STL files
    import_labelmap(labelmap_path, ref_vol_id)     — load NIfTI mask → segmentation node
"""
from __future__ import annotations
import json
from ..controller.service import controller
from ..slicer.session import SlicerSession

ns = controller.namespace("segmentation", "Create, threshold, export, and import segmentations")


@ns.action("Create an empty segmentation node with optional reference volume geometry")
async def create_segmentation(
    session: SlicerSession,
    name: str = "Segmentation",
    ref_volume_id: str = "",
) -> dict:
    """Returns {id, name}."""
    resp = await session.run_checked(f"""
import slicer
seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", {json.dumps(name)})
seg.CreateDefaultDisplayNodes()
if {json.dumps(ref_volume_id)}:
    ref = slicer.mrmlScene.GetNodeByID({json.dumps(ref_volume_id)})
    if ref:
        seg.SetReferenceImageGeometryParameterFromVolumeNode(ref)
__result__ = {{"id": seg.GetID(), "name": seg.GetName()}}
""")
    return resp["result"]


@ns.action("Add a named empty segment to a segmentation node")
async def add_segment(
    session: SlicerSession,
    seg_node_id: str,
    name: str,
    color: list | None = None,
) -> str:
    """color: [r, g, b] floats 0–1. Returns the segment ID string."""
    color_code = json.dumps(color or [1.0, 0.0, 0.0])
    resp = await session.run_checked(f"""
import slicer
seg = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
sid = seg.GetSegmentation().AddEmptySegment({json.dumps(name)})
segment = seg.GetSegmentation().GetSegment(sid)
segment.SetName({json.dumps(name)})
color = {color_code}
segment.SetColor(color[0], color[1], color[2])
__result__ = sid
""")
    return resp["result"]


@ns.action(
    "Segment a volume by intensity threshold using numpy (headless-safe, no GUI widget)"
)
async def threshold_segment(
    session: SlicerSession,
    seg_node_id: str,
    segment_name: str,
    volume_id: str,
    min_threshold: float,
    max_threshold: float,
) -> dict:
    """
    Sets voxels in [min_threshold, max_threshold] to 1, rest to 0.
    Creates the named segment if it doesn't exist.
    Returns {seg_node_id, segment_id, voxel_count}.
    """
    resp = await session.run_checked(f"""
import slicer, numpy as np
seg = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
vol = slicer.mrmlScene.GetNodeByID({json.dumps(volume_id)})
segmentation = seg.GetSegmentation()

# Find or create the segment (search by display name)
sid = segmentation.GetSegmentIdBySegmentName({json.dumps(segment_name)})
if not sid:
    # fall back: check if there's an ID matching the name
    existing = segmentation.GetSegment({json.dumps(segment_name)})
    if existing:
        sid = {json.dumps(segment_name)}
    else:
        sid = segmentation.AddEmptySegment({json.dumps(segment_name)})
        segmentation.GetSegment(sid).SetName({json.dumps(segment_name)})

# Apply threshold via numpy
lo, hi = {min_threshold}, {max_threshold}
vol_arr = slicer.util.arrayFromVolume(vol)
seg_arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg, sid, vol)
seg_arr[:] = 0
seg_arr[(vol_arr >= lo) & (vol_arr <= hi)] = 1
slicer.util.updateSegmentBinaryLabelmapFromArray(seg_arr, seg, sid, vol)

voxel_count = int(np.sum(seg_arr))
__result__ = {{"seg_node_id": seg.GetID(), "segment_id": sid, "voxel_count": voxel_count}}
""")
    return resp["result"]


@ns.action("Compute per-segment statistics: volume mm3, surface area mm2, centroid RAS")
async def get_segment_stats(
    session: SlicerSession,
    seg_node_id: str,
    volume_id: str = "",
) -> list:
    """
    Returns list of dicts: {segment_id, name, volume_mm3, surface_area_mm2, centroid_ras}.
    volume_id is optional; omit for geometry-only stats.
    """
    resp = await session.run_checked(f"""
import slicer
import SegmentStatistics

seg = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
logic = SegmentStatistics.SegmentStatisticsLogic()
pn = logic.getParameterNode()
pn.SetParameter("Segmentation", seg.GetID())
pn.SetParameter("LabelmapSegmentStatisticsPlugin.centroid_ras.enabled", "True")
pn.SetParameter("LabelmapSegmentStatisticsPlugin.surface_area_mm2.enabled", "True")
if {json.dumps(volume_id)}:
    vol = slicer.mrmlScene.GetNodeByID({json.dumps(volume_id)})
    if vol:
        pn.SetParameter("ScalarVolume", vol.GetID())

logic.computeStatistics()
stats = logic.getStatistics()

results = []
for sid in stats["SegmentIDs"]:
    s = seg.GetSegmentation().GetSegment(sid)
    entry = {{
        "segment_id":       sid,
        "name":             s.GetName(),
        "volume_mm3":       stats.get((sid, "LabelmapSegmentStatisticsPlugin.volume_mm3")),
        "surface_area_mm2": stats.get((sid, "LabelmapSegmentStatisticsPlugin.surface_area_mm2")),
        "centroid_ras":     stats.get((sid, "LabelmapSegmentStatisticsPlugin.centroid_ras")),
    }}
    results.append(entry)
__result__ = results
""")
    return resp["result"]


@ns.action("Export a segmentation node to NIfTI (.nii.gz) as a labelmap")
async def export_segmentation_nifti(
    session: SlicerSession,
    seg_node_id: str,
    path: str,
    ref_volume_id: str = "",
) -> str:
    """Creates a temporary labelmap node, exports it to path, removes the labelmap. Returns path."""
    resp = await session.run_checked(f"""
import slicer
seg = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
lm = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
if {json.dumps(ref_volume_id)}:
    ref = slicer.mrmlScene.GetNodeByID({json.dumps(ref_volume_id)})
    slicer.modules.segmentations.logic().ExportVisibleSegmentsToLabelmapNode(seg, lm, ref)
else:
    slicer.modules.segmentations.logic().ExportAllSegmentsToLabelmapNode(
        seg, lm, slicer.vtkSegmentation.EXTENT_REFERENCE_GEOMETRY)
slicer.util.exportNode(lm, {json.dumps(path)})
slicer.mrmlScene.RemoveNode(lm)
__result__ = {json.dumps(path)}
""")
    return resp["result"]


@ns.action("Export all segments of a segmentation as STL files to a directory")
async def export_segmentation_stl(
    session: SlicerSession,
    seg_node_id: str,
    output_dir: str,
    format: str = "STL",
) -> str:
    """
    format: 'STL' or 'OBJ'. Creates output_dir if needed.
    Returns output_dir.
    """
    resp = await session.run_checked(f"""
import slicer, os
seg = slicer.mrmlScene.GetNodeByID({json.dumps(seg_node_id)})
out = {json.dumps(output_dir)}
os.makedirs(out, exist_ok=True)
seg.CreateClosedSurfaceRepresentation()
slicer.vtkSlicerSegmentationsModuleLogic.ExportSegmentsClosedSurfaceRepresentationToFiles(
    out, seg, None, {json.dumps(format)})
__result__ = out
""")
    return resp["result"]


@ns.action("Load a NIfTI labelmap mask file and import it as a segmentation node")
async def import_labelmap(
    session: SlicerSession,
    labelmap_path: str,
    ref_volume_id: str = "",
    name: str = "ImportedSegmentation",
) -> dict:
    """Returns {id, name, num_segments} of the created segmentation node."""
    resp = await session.run_checked(f"""
import slicer
lm = slicer.util.loadLabelVolume({json.dumps(labelmap_path)})
seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", {json.dumps(name)})
if {json.dumps(ref_volume_id)}:
    ref = slicer.mrmlScene.GetNodeByID({json.dumps(ref_volume_id)})
    if ref:
        seg.SetReferenceImageGeometryParameterFromVolumeNode(ref)
slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(lm, seg)
slicer.mrmlScene.RemoveNode(lm)
__result__ = {{
    "id":           seg.GetID(),
    "name":         seg.GetName(),
    "num_segments": seg.GetSegmentation().GetNumberOfSegments(),
}}
""")
    return resp["result"]
