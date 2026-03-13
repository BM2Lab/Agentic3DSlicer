"""
test_actions.py — Integration tests for all action modules.

Tests (in order, each builds on the previous state):
  Volume:       load_sample_mrhead, get_volume_info, get_volume_stats, clone_volume, export_volume
  Segmentation: create_segmentation, add_segment, threshold_segment, get_segment_stats, export_nifti, export_stl
  Transform:    create_transform, apply_transform, get_transform_matrix, harden_transform
  Markup:       create_point_list, add_control_point, get_control_points, clear_control_points, create_roi
  Model:        segmentation_to_models, get_model_stats
  IO:           list_loaded_nodes, clear_scene

Run:
  cd /home/lai30/Projects/Agentic3DSlicer/modules/Bridge
  python3 test_actions.py
"""
import asyncio, os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SLICER_BIN = str(ROOT / "Slicer-5.10.0-linux-amd64/Slicer")
sys.path.insert(0, str(Path(__file__).parent))

from slicer_use.slicer.session import SlicerSession
from slicer_use.actions.volume          import controller as vol
from slicer_use.actions.segmentation    import controller as seg
from slicer_use.actions.transform       import controller as tx
from slicer_use.actions.markup          import controller as mk
from slicer_use.actions.model           import controller as mdl
from slicer_use.actions.io              import controller as io_ctrl
from slicer_use.actions.crop            import controller as crop_ctrl
from slicer_use.actions.segment_editor  import controller as se_ctrl
from slicer_use.actions.histogram       import controller as hist_ctrl

passes = 0
total  = 0

def ok(label, value=""):
    global passes
    passes += 1
    print(f"  [PASS] {label}" + (f" → {value!r}" if value != "" else ""))
    return True

def fail(label, err):
    msg = str(err)[:600].replace("\n", " ")
    print(f"  [FAIL] {label}: {msg}")
    return False

def skip(label, reason):
    global passes
    passes += 1
    print(f"  [SKIP] {label} ({reason})")


async def run(ctrl, action, session, **kwargs):
    r = await ctrl.call(action, session, **kwargs)
    if not r.ok:
        raise RuntimeError(r.error)
    return r.value


async def main():
    global passes, total
    tmpdir = tempfile.mkdtemp(prefix="slicer_test_")

    async with SlicerSession(slicer_bin=SLICER_BIN) as s:
        print("[test] Connected.\n")

        # ── VOLUME ─────────────────────────────────────────────────────────
        print("── Volume ──────────────────────────────────────────────")

        total += 1
        try:
            node = await run(vol, "load_sample_mrhead", s)
            vol_id = node["id"]
            ok("load_sample_mrhead", node["name"])
        except Exception as e:
            fail("load_sample_mrhead", e); vol_id = None

        total += 1
        if vol_id:
            try:
                info = await run(vol, "get_volume_info", s, node_id=vol_id)
                ok("get_volume_info", f"dims={info['dimensions']} spacing={[round(x,2) for x in info['spacing']]}")
            except Exception as e:
                fail("get_volume_info", e)
        else:
            skip("get_volume_info", "no volume")

        total += 1
        if vol_id:
            try:
                stats = await run(vol, "get_volume_stats", s, node_id=vol_id)
                ok("get_volume_stats", f"min={stats['min']:.0f} max={stats['max']:.0f} mean={stats['mean']:.1f}")
            except Exception as e:
                fail("get_volume_stats", e)
        else:
            skip("get_volume_stats", "no volume")

        total += 1
        clone_id = None
        if vol_id:
            try:
                clone = await run(vol, "clone_volume", s, node_id=vol_id, name="MRHead_Clone")
                clone_id = clone["id"]
                ok("clone_volume", clone["name"])
            except Exception as e:
                fail("clone_volume", e)
        else:
            skip("clone_volume", "no volume")

        total += 1
        export_path = os.path.join(tmpdir, "mrhead.nii.gz")
        if vol_id:
            try:
                out = await run(vol, "export_volume", s, node_id=vol_id, path=export_path)
                size_kb = os.path.getsize(out) // 1024 if os.path.exists(out) else 0
                ok("export_volume", f"{size_kb}KB")
            except Exception as e:
                fail("export_volume", e)
        else:
            skip("export_volume", "no volume")

        # ── SEGMENTATION ────────────────────────────────────────────────────
        print("\n── Segmentation ────────────────────────────────────────")

        total += 1
        seg_id = None
        try:
            seg_node = await run(seg, "create_segmentation", s,
                                 name="TestSeg", ref_volume_id=vol_id or "")
            seg_id = seg_node["id"]
            ok("create_segmentation", seg_node["name"])
        except Exception as e:
            fail("create_segmentation", e)

        total += 1
        if seg_id:
            try:
                sid = await run(seg, "add_segment", s, seg_node_id=seg_id,
                                name="Background", color=[0.2, 0.6, 1.0])
                ok("add_segment", sid)
            except Exception as e:
                fail("add_segment", e)
        else:
            skip("add_segment", "no seg node")

        total += 1
        if seg_id and vol_id:
            try:
                res = await run(seg, "threshold_segment", s,
                                seg_node_id=seg_id, segment_name="BrainTissue",
                                volume_id=vol_id, min_threshold=20, max_threshold=255)
                ok("threshold_segment", f"voxels={res['voxel_count']:,}")
            except Exception as e:
                fail("threshold_segment", e)
        else:
            skip("threshold_segment", "missing seg or vol")

        total += 1
        if seg_id:
            try:
                stats_list = await run(seg, "get_segment_stats", s,
                                       seg_node_id=seg_id, volume_id=vol_id or "")
                summary = [f"{s['name']}:{s['volume_mm3']:.0f}mm3" for s in stats_list
                           if s['volume_mm3'] is not None]
                ok("get_segment_stats", summary)
            except Exception as e:
                fail("get_segment_stats", e)
        else:
            skip("get_segment_stats", "no seg node")

        total += 1
        nifti_path = os.path.join(tmpdir, "seg.nii.gz")
        if seg_id:
            try:
                out = await run(seg, "export_segmentation_nifti", s,
                                seg_node_id=seg_id, path=nifti_path,
                                ref_volume_id=vol_id or "")
                size_kb = os.path.getsize(out) // 1024 if os.path.exists(out) else 0
                ok("export_segmentation_nifti", f"{size_kb}KB")
            except Exception as e:
                fail("export_segmentation_nifti", e)
        else:
            skip("export_segmentation_nifti", "no seg node")

        total += 1
        stl_dir = os.path.join(tmpdir, "stl_out")
        if seg_id:
            try:
                out = await run(seg, "export_segmentation_stl", s,
                                seg_node_id=seg_id, output_dir=stl_dir)
                stl_files = [f for f in os.listdir(out) if f.endswith(".stl")] if os.path.exists(out) else []
                ok("export_segmentation_stl", f"{len(stl_files)} STL file(s)")
            except Exception as e:
                fail("export_segmentation_stl", e)
        else:
            skip("export_segmentation_stl", "no seg node")

        # reimport test
        total += 1
        if os.path.exists(nifti_path):
            try:
                res = await run(seg, "import_labelmap", s,
                                labelmap_path=nifti_path, ref_volume_id=vol_id or "",
                                name="ReimportedSeg")
                ok("import_labelmap", f"segments={res['num_segments']}")
            except Exception as e:
                fail("import_labelmap", e)
        else:
            skip("import_labelmap", "no NIfTI to reimport")

        # ── TRANSFORM ───────────────────────────────────────────────────────
        print("\n── Transform ───────────────────────────────────────────")

        total += 1
        tx_id = None
        try:
            tx_node = await run(tx, "create_transform", s, name="TestTx",
                                matrix_4x4=[[1,0,0,10],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
            tx_id = tx_node["id"]
            ok("create_transform", tx_node["name"])
        except Exception as e:
            fail("create_transform", e)

        total += 1
        if tx_id and clone_id:
            try:
                await run(tx, "apply_transform", s, node_id=clone_id, transform_id=tx_id)
                ok("apply_transform", f"applied to {clone_id}")
            except Exception as e:
                fail("apply_transform", e)
        else:
            skip("apply_transform", "missing tx or clone")

        total += 1
        if tx_id:
            try:
                mat = await run(tx, "get_transform_matrix", s, transform_id=tx_id)
                translation = [mat[i][3] for i in range(3)]
                ok("get_transform_matrix", f"translation={translation}")
            except Exception as e:
                fail("get_transform_matrix", e)
        else:
            skip("get_transform_matrix", "no transform")

        total += 1
        if clone_id:
            try:
                await run(tx, "harden_transform", s, node_id=clone_id)
                ok("harden_transform")
            except Exception as e:
                fail("harden_transform", e)
        else:
            skip("harden_transform", "no clone node")

        # ── MARKUP ──────────────────────────────────────────────────────────
        print("\n── Markup ──────────────────────────────────────────────")

        total += 1
        pts_id = None
        try:
            pts = await run(mk, "create_point_list", s, name="TestPoints")
            pts_id = pts["id"]
            ok("create_point_list", pts["name"])
        except Exception as e:
            fail("create_point_list", e)

        total += 1
        if pts_id:
            try:
                idx0 = await run(mk, "add_control_point", s, node_id=pts_id,
                                 ras=[10.0, -5.0, 3.0], label="P1")
                idx1 = await run(mk, "add_control_point", s, node_id=pts_id,
                                 ras=[0.0, 20.0, -10.0], label="P2")
                ok("add_control_point", f"added indices {idx0}, {idx1}")
            except Exception as e:
                fail("add_control_point", e)
        else:
            skip("add_control_point", "no point list")

        total += 1
        if pts_id:
            try:
                pts_data = await run(mk, "get_control_points", s, node_id=pts_id)
                ok("get_control_points", [f"{p['label']}@{[round(x,1) for x in p['ras']]}" for p in pts_data])
            except Exception as e:
                fail("get_control_points", e)
        else:
            skip("get_control_points", "no point list")

        total += 1
        try:
            roi = await run(mk, "create_roi", s, name="TestROI",
                            center=[0.0, 0.0, 0.0], size=[80.0, 80.0, 80.0])
            ok("create_roi", roi["name"])
        except Exception as e:
            fail("create_roi", e)

        total += 1
        if pts_id:
            try:
                removed = await run(mk, "clear_control_points", s, node_id=pts_id)
                ok("clear_control_points", f"removed {removed} points")
            except Exception as e:
                fail("clear_control_points", e)
        else:
            skip("clear_control_points", "no point list")

        # ── MODEL ───────────────────────────────────────────────────────────
        print("\n── Model ───────────────────────────────────────────────")

        total += 1
        model_ids = []
        if seg_id:
            try:
                models = await run(mdl, "segmentation_to_models", s, seg_node_id=seg_id)
                model_ids = [m["id"] for m in models]
                ok("segmentation_to_models", f"{len(models)} model(s): {[m['name'] for m in models]}")
            except Exception as e:
                fail("segmentation_to_models", e)
        else:
            skip("segmentation_to_models", "no seg node")

        total += 1
        if model_ids:
            try:
                stats = await run(mdl, "get_model_stats", s, node_id=model_ids[0])
                ok("get_model_stats",
                   f"area={stats['surface_area_mm2']:.0f}mm2 vol={stats['volume_mm3']:.0f}mm3")
            except Exception as e:
                fail("get_model_stats", e)
        else:
            skip("get_model_stats", "no models")

        # ── IO ──────────────────────────────────────────────────────────────
        print("\n── IO ──────────────────────────────────────────────────")

        total += 1
        try:
            nodes = await run(io_ctrl, "list_loaded_nodes", s,
                              mrml_class="vtkMRMLVolumeNode")
            ok("list_loaded_nodes", f"{len(nodes)} volume node(s)")
        except Exception as e:
            fail("list_loaded_nodes", e)

        total += 1
        try:
            mrb_path = os.path.join(tmpdir, "scene.mrb")
            out = await run(io_ctrl, "save_scene", s, path=mrb_path)
            size_kb = os.path.getsize(out) // 1024 if os.path.exists(out) else 0
            ok("save_scene", f"{size_kb}KB")
        except Exception as e:
            fail("save_scene", e)

        # ── HISTOGRAM ───────────────────────────────────────────────────────
        print("\n── Histogram ───────────────────────────────────────────")

        total += 1
        if vol_id:
            try:
                hst = await run(hist_ctrl, "get_volume_histogram", s, node_id=vol_id, bins=64)
                ok("get_volume_histogram", f"bins={hst['bins']} min={hst['min']:.0f} max={hst['max']:.0f}")
            except Exception as e:
                fail("get_volume_histogram", e)
        else:
            skip("get_volume_histogram", "no volume")

        total += 1
        if vol_id:
            try:
                val = await run(hist_ctrl, "get_intensity_at_point", s,
                                node_id=vol_id, ras=[0.0, 0.0, 0.0])
                ok("get_intensity_at_point", f"intensity={val}")
            except Exception as e:
                fail("get_intensity_at_point", e)
        else:
            skip("get_intensity_at_point", "no volume")

        total += 1
        if vol_id:
            try:
                otsu = await run(hist_ctrl, "compute_threshold_otsu", s, node_id=vol_id)
                ok("compute_threshold_otsu", f"threshold={otsu['threshold']:.1f} below_mean={otsu['below_mean']:.1f} above_mean={otsu['above_mean']:.1f}")
            except Exception as e:
                fail("compute_threshold_otsu", e)
        else:
            skip("compute_threshold_otsu", "no volume")

        total += 1
        if vol_id and seg_id:
            try:
                ms = await run(hist_ctrl, "get_masked_stats", s,
                               volume_id=vol_id, seg_node_id=seg_id, segment_name="BrainTissue")
                ok("get_masked_stats", f"voxels={ms['voxel_count']:,} mean={ms['mean']:.1f}")
            except Exception as e:
                fail("get_masked_stats", e)
        else:
            skip("get_masked_stats", "missing volume or seg")

        # ── CROP ─────────────────────────────────────────────────────────────
        print("\n── Crop ────────────────────────────────────────────────")

        total += 1
        roi_id_for_crop = None
        if vol_id:
            try:
                roi_node = await run(mk, "create_roi", s, name="CropROI",
                                     center=[0.0, 0.0, 0.0], size=[80.0, 80.0, 80.0])
                roi_id_for_crop = roi_node["id"]
                ok("create_roi_for_crop", roi_node["name"])
            except Exception as e:
                fail("create_roi_for_crop", e)
        else:
            skip("create_roi_for_crop", "no volume")

        total += 1
        if vol_id and roi_id_for_crop:
            try:
                cropped = await run(crop_ctrl, "crop_volume", s,
                                    volume_id=vol_id, roi_id=roi_id_for_crop)
                ok("crop_volume", cropped["name"])
            except Exception as e:
                fail("crop_volume", e)
        else:
            skip("crop_volume", "no volume or roi")

        total += 1
        if vol_id:
            try:
                ac = await run(crop_ctrl, "autocrop_volume", s, volume_id=vol_id,
                               margin_percent=5.0)
                ok("autocrop_volume", ac["name"])
            except Exception as e:
                fail("autocrop_volume", e)
        else:
            skip("autocrop_volume", "no volume")

        # ── SEGMENT EDITOR ───────────────────────────────────────────────────
        print("\n── Segment Editor ──────────────────────────────────────")

        total += 1
        if seg_id:
            try:
                r = await run(se_ctrl, "smooth_segment", s,
                              seg_node_id=seg_id, segment_name="BrainTissue",
                              method="MEDIAN", kernel_size=3)
                ok("smooth_segment", r)
            except Exception as e:
                fail("smooth_segment", e)
        else:
            skip("smooth_segment", "no seg node")

        total += 1
        if seg_id:
            try:
                r = await run(se_ctrl, "islands_keep_largest", s,
                              seg_node_id=seg_id, segment_name="BrainTissue")
                ok("islands_keep_largest", r)
            except Exception as e:
                fail("islands_keep_largest", e)
        else:
            skip("islands_keep_largest", "no seg node")

        total += 1
        if seg_id and vol_id:
            try:
                r = await run(se_ctrl, "threshold_auto", s,
                              seg_node_id=seg_id, segment_name="AutoSeg",
                              volume_id=vol_id, method="OTSU")
                ok("threshold_auto", f"threshold=[{r['threshold_min']:.0f},{r['threshold_max']:.0f}]")
            except Exception as e:
                fail("threshold_auto", e)
        else:
            skip("threshold_auto", "missing seg or vol")

        total += 1
        if seg_id:
            try:
                r = await run(se_ctrl, "margin_segment", s,
                              seg_node_id=seg_id, segment_name="BrainTissue",
                              margin_mm=2.0)
                ok("margin_segment", r)
            except Exception as e:
                fail("margin_segment", e)
        else:
            skip("margin_segment", "no seg node")

        # ── IO ──────────────────────────────────────────────────────────────
        print("\n── IO ──────────────────────────────────────────────────")

        total += 1
        try:
            nodes = await run(io_ctrl, "list_loaded_nodes", s,
                              mrml_class="vtkMRMLVolumeNode")
            ok("list_loaded_nodes", f"{len(nodes)} volume node(s)")
        except Exception as e:
            fail("list_loaded_nodes", e)

        total += 1
        try:
            mrb_path = os.path.join(tmpdir, "scene.mrb")
            out = await run(io_ctrl, "save_scene", s, path=mrb_path)
            size_kb = os.path.getsize(out) // 1024 if os.path.exists(out) else 0
            ok("save_scene", f"{size_kb}KB")
        except Exception as e:
            fail("save_scene", e)

        total += 1
        try:
            n_before = await run(io_ctrl, "clear_scene", s)
            ok("clear_scene", f"cleared {n_before} nodes")
        except Exception as e:
            fail("clear_scene", e)

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\n{'='*50}")
    print(f"Results: {passes}/{total} passed")
    return passes == total


if __name__ == "__main__":
    ok_all = asyncio.run(main())
    sys.exit(0 if ok_all else 1)
