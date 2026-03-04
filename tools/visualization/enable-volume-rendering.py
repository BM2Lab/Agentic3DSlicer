"""
Tool:        enable-volume-rendering.py
Category:    visualization
Tags:        volume rendering, render, 3D, preset, MR-Default, CT-Bone, CT-Chest, MR-MIP, vtkMRMLVolumeRenderingDisplayNode
Description: Enable volume rendering on a loaded scalar volume with a named preset
Usage:       Set `volumeNode` before running. Optionally set `preset_name`.
             Verified presets: "MR-Default", "MR-MIP", "CT-Chest", "CT-Bone"
Version:     1.0
Verified:    2026-03-04  (Slicer 5.10.0)

Notes:
- Logic API: slicer.modules.volumerendering.logic()
- CreateDefaultVolumeRenderingDisplayNode() does NOT exist — use CreateVolumeRenderingDisplayNode()
- ApplyPreset() does NOT exist — copy preset node directly:
    displayNode.GetVolumePropertyNode().Copy(presetNode)
- GetPresetByName() returns a vtkMRMLVolumePropertyNode
"""
import slicer

def enable_volume_rendering(volumeNode, preset_name="MR-Default"):
    volRenLogic = slicer.modules.volumerendering.logic()

    # Create and register display node
    displayNode = volRenLogic.CreateVolumeRenderingDisplayNode()
    slicer.mrmlScene.AddNode(displayNode)
    displayNode.UnRegister(volRenLogic)

    # Link to volume and update from volume's scalar display
    volRenLogic.UpdateDisplayNodeFromVolumeNode(displayNode, volumeNode)
    volumeNode.AddAndObserveDisplayNodeID(displayNode.GetID())

    # Apply preset by copying its VolumePropertyNode
    presetNode = volRenLogic.GetPresetByName(preset_name)
    if presetNode:
        displayNode.GetVolumePropertyNode().Copy(presetNode)
        print(f"Applied preset: {preset_name}")
    else:
        print(f"Warning: preset '{preset_name}' not found, using default")

    displayNode.SetVisibility(True)

    # Reset camera and force render
    layoutMgr = slicer.app.layoutManager()
    threeDView = layoutMgr.threeDWidget(0).threeDView()
    threeDView.resetFocalPoint()
    slicer.util.forceRenderAllViews()
    slicer.app.processEvents()

    print(f"Volume rendering enabled for: {volumeNode.GetName()}")
    return displayNode


# Example usage:
# volumeNode = slicer.util.getNode("MRHead")
# enable_volume_rendering(volumeNode, "MR-Default")
