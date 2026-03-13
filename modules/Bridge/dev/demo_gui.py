"""
demo_gui.py — Open Slicer with GUI window and run simple actions.

Actions performed:
  1. Load MRHead sample volume
  2. Show volume in all slice views and 3D view
  3. Add three landmark fiducial points
  4. Add an ROI box around the head
  5. Create a 10mm translation transform (visible in Data module)
  6. Print scene summary

The Slicer window stays open for inspection after the script finishes.

Run:
  cd /home/lai30/Projects/Agentic3DSlicer/modules/Bridge
  python3 demo_gui.py
"""
import asyncio, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SLICER_BIN = str(ROOT / "Slicer-5.10.0-linux-amd64/Slicer")
sys.path.insert(0, str(Path(__file__).parent))

from slicer_use.slicer.session import SlicerSession
from slicer_use.actions.volume    import controller as vol
from slicer_use.actions.markup    import controller as mk
from slicer_use.actions.transform import controller as tx
from slicer_use.actions.io        import controller as io_ctrl


async def main():
    print("Starting Slicer in GUI mode (window will appear)...")
    print("This takes ~30-60s for the GUI to load.\n")

    # GUI mode: no_main_window=False, longer startup timeout
    session = SlicerSession(
        slicer_bin=SLICER_BIN,
        no_main_window=False,
        startup_timeout=120.0,
    )
    await session.start()
    print("Connected to Slicer.\n")

    # ── 1. Load MRHead ───────────────────────────────────────────────────────
    print("Loading MRHead sample volume...")
    r = await vol.call("load_sample_mrhead", session)
    vol_node = r.value
    print(f"  Loaded: {vol_node['name']} (id={vol_node['id']})")

    # ── 2. Configure layout via MRML (no blocking Qt calls) ──────────────────
    print("Configuring layout node...")
    await session.run_checked(f"""
import slicer
# Set Four-Up layout through the MRML layout node (non-blocking)
layoutNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLLayoutNode")
if layoutNode:
    layoutNode.SetViewArrangement(
        slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
__result__ = "layout set"
""")
    print("  Layout set to Four-Up.")

    # ── 3. Add landmark fiducial points ──────────────────────────────────────
    print("Adding landmark points...")
    r = await mk.call("create_point_list", session, name="LandmarkPoints")
    pts_id = r.value["id"]

    landmarks = [
        ([0.0,   70.0,  10.0], "Apex"),
        ([0.0,  -40.0, -30.0], "Base"),
        ([50.0,   0.0,   0.0], "Right"),
        ([-50.0,  0.0,   0.0], "Left"),
    ]
    for ras, label in landmarks:
        await mk.call("add_control_point", session, node_id=pts_id, ras=ras, label=label)
        print(f"  Point {label} @ {ras}")

    # ── 4. Add ROI ───────────────────────────────────────────────────────────
    print("Adding ROI box...")
    r = await mk.call("create_roi", session,
                      name="HeadROI",
                      center=[0.0, 10.0, 0.0],
                      size=[160.0, 200.0, 180.0])
    print(f"  ROI: {r.value['name']} (id={r.value['id']})")

    # ── 5. Create a transform ────────────────────────────────────────────────
    print("Creating example transform (10mm R translation)...")
    r = await tx.call("create_transform", session,
                      name="DemoTransform",
                      matrix_4x4=[[1,0,0,10],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
    print(f"  Transform: {r.value['name']} (id={r.value['id']})")

    # ── 6. Show scene summary ────────────────────────────────────────────────
    print("\nScene summary:")
    r = await io_ctrl.call("list_loaded_nodes", session, mrml_class="vtkMRMLNode")
    for node in r.value:
        print(f"  {node['class']:<40} {node['name']}")

    # ── Keep window open ─────────────────────────────────────────────────────
    print("\n" + "="*55)
    print("Slicer window is open. Inspect it, then close it manually")
    print("or press Ctrl+C here to terminate.")
    print("="*55)

    try:
        # Wait indefinitely until user closes Slicer or presses Ctrl+C
        await asyncio.get_event_loop().run_in_executor(
            None, session._proc.wait
        )
        print("\nSlicer window closed.")
    except KeyboardInterrupt:
        print("\nCtrl+C received — terminating Slicer.")
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
