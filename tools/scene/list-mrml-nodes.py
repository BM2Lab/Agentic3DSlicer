"""
Tool:        list-mrml-nodes.py
Category:    scene
Tags:        mrml, nodes, scene, list, inspect, debug, vtkMRMLNode
Description: List all MRML nodes in the current scene with index, class, and name
Usage:       Run inside Slicer's Python environment
Version:     1.0
Verified:    2026-03-04  (Slicer 5.10.0, 118 default nodes on startup)
"""
import slicer

def list_mrml_nodes(save_path=None):
    scene = slicer.mrmlScene
    col = scene.GetNodes()
    nodes = []
    for i in range(col.GetNumberOfItems()):
        node = col.GetItemAsObject(i)
        nodes.append(f"[{i:03d}] {node.GetClassName():<40} name={node.GetName()}")

    print(f"Total nodes: {len(nodes)}")
    for line in nodes:
        print(line)

    if save_path:
        with open(save_path, "w") as f:
            f.write(f"Total nodes: {len(nodes)}\n")
            f.write("\n".join(nodes))
        print(f"Saved to {save_path}")

    return nodes


# Example usage:
# list_mrml_nodes("/tmp/nodes.txt")
