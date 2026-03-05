"""
Tool:        fiducial-registration.py
Category:    scene
Tags:        fiducial, registration, IGT, FiducialRegistrationWizard, transform, RMS, error, SlicerIGT
Description: Register two fiducial point sets (NodeA → NodeB) using SlicerIGT
             FiducialRegistrationWizard. Returns the 4x4 rigid transform and RMS error.
Usage:       Run inside Slicer Python environment after SlicerIGT is installed.
             Set nodeA, nodeB, and output_path before calling run_fiducial_registration().
Version:     1.0
Verified:    2026-03-04  (Slicer 5.10.0, SlicerIGT rev 42091cd)

Notes:
- Requires SlicerIGT extension (install via install-extension.py first)
- Correct API: logic.UpdateCalibration(wizardNode) — takes ONE vtkMRMLFiducialRegistrationWizardNode
- Wrong API (do NOT use): logic.UpdateCalibration(nodeA, nodeB, transform, mode, rmsRef)
- wizardNode.GetCalibrationError() returns RMS error in mm
- wizardNode.GetCalibrationStatusMessage() returns human-readable status
"""
import slicer

def run_fiducial_registration(nodeA, nodeB, output_path=None):
    """
    Args:
        nodeA: vtkMRMLMarkupsFiducialNode — fixed/reference points
        nodeB: vtkMRMLMarkupsFiducialNode — moving points
        output_path: optional path to save results as .txt
    Returns:
        dict with keys: rms_error, matrix (4x4 list), status_message, transform_node
    """
    import vtk

    if not hasattr(slicer.modules, 'fiducialregistrationwizard'):
        raise RuntimeError("FiducialRegistrationWizard module not loaded. Install SlicerIGT first.")

    transformNode = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLLinearTransformNode", "FiducialReg_Transform")

    wizardNode = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLFiducialRegistrationWizardNode", "FiducialRegWizard")
    wizardNode.SetAndObserveFromFiducialListNodeId(nodeA.GetID())
    wizardNode.SetAndObserveToFiducialListNodeId(nodeB.GetID())
    wizardNode.SetOutputTransformNodeId(transformNode.GetID())

    logic = slicer.modules.fiducialregistrationwizard.logic()
    logic.UpdateCalibration(wizardNode)

    rms = wizardNode.GetCalibrationError()
    status = wizardNode.GetCalibrationStatusMessage()

    matrix = vtk.vtkMatrix4x4()
    transformNode.GetMatrixTransformToParent(matrix)
    rows = [[matrix.GetElement(r, c) for c in range(4)] for r in range(4)]

    print(f"Status   : {status}")
    print(f"RMS Error: {rms:.4f} mm")
    print("4x4 Transform Matrix:")
    for row in rows:
        print("  [ " + "  ".join(f"{v:10.5f}" for v in row) + " ]")

    if output_path:
        with open(output_path, "w") as f:
            f.write(f"Status         : {status}\n")
            f.write(f"RMS Error      : {rms:.4f} mm\n\n")
            f.write("4x4 Transform Matrix (NodeA -> NodeB):\n")
            for row in rows:
                f.write("  [ " + "  ".join(f"{v:10.5f}" for v in row) + " ]\n")
        print(f"Saved: {output_path}")

    return {"rms_error": rms, "matrix": rows, "status_message": status,
            "transform_node": transformNode}


# Example usage:
# nodeA = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "NodeA")
# nodeA.AddControlPoint(10, 20, 30); nodeA.AddControlPoint(60, 10, 5); nodeA.AddControlPoint(30, -20, 50)
# nodeB = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "NodeB")
# nodeB.AddControlPoint(12, 21, 32); nodeB.AddControlPoint(62, 11, 6.5); nodeB.AddControlPoint(31.5, -19, 51)
# result = run_fiducial_registration(nodeA, nodeB, "/tmp/reg_result.txt")
