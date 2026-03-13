"""
IO / Scene actions — load DICOM, clear scene, save scene, generic node export.

Actions:
    load_dicom(dicom_dir)       — import DICOM directory, load all patients
    clear_scene()               — remove all nodes from the MRML scene
    save_scene(path)            — save as .mrb (Medical Reality Bundle)
    list_loaded_nodes(class_)   — list nodes of a given class
"""
from __future__ import annotations
import json
from ..controller.service import controller
from ..slicer.session import SlicerSession

ns = controller.namespace("io", "DICOM import, scene save/clear, generic node listing")


@ns.action("Import a DICOM directory and load all patients; returns list of loaded node ids")
async def load_dicom(session: SlicerSession, dicom_dir: str) -> list:
    """
    Uses DICOMLib.DICOMUtils. Returns list of {id, name} for every loaded node.
    Note: DICOM loading can be slow for large datasets.
    """
    resp = await session.run_checked(f"""
import slicer
from DICOMLib import DICOMUtils
loaded_ids = []
with DICOMUtils.TemporaryDICOMDatabase() as db:
    DICOMUtils.importDicom({json.dumps(dicom_dir)}, db)
    for patient_uid in db.patients():
        loaded_ids.extend(DICOMUtils.loadPatientByUID(patient_uid))

nodes = []
for nid in loaded_ids:
    n = slicer.mrmlScene.GetNodeByID(nid)
    if n:
        nodes.append({{"id": n.GetID(), "name": n.GetName()}})
__result__ = nodes
""")
    return resp["result"]


@ns.action("Clear all nodes from the MRML scene")
async def clear_scene(session: SlicerSession) -> int:
    """Returns the number of nodes that were in the scene before clearing."""
    resp = await session.run_checked("""
import slicer
n = slicer.mrmlScene.GetNumberOfNodes()
slicer.mrmlScene.Clear()
__result__ = n
""")
    return resp["result"]


@ns.action("Save the entire scene to a .mrb file (Medical Reality Bundle)")
async def save_scene(session: SlicerSession, path: str) -> str:
    """Returns the output path."""
    resp = await session.run_checked(f"""
import slicer
slicer.util.saveScene({json.dumps(path)})
__result__ = {json.dumps(path)}
""")
    return resp["result"]


@ns.action("List all scene nodes of a given MRML class (e.g. vtkMRMLVolumeNode)")
async def list_loaded_nodes(
    session: SlicerSession,
    mrml_class: str = "vtkMRMLVolumeNode",
) -> list:
    """Returns list of {id, name, class} dicts."""
    resp = await session.run_checked(f"""
import slicer
nodes = slicer.util.getNodesByClass({json.dumps(mrml_class)})
__result__ = [{{"id": n.GetID(), "name": n.GetName(), "class": n.GetClassName()}} for n in nodes]
""")
    return resp["result"]
