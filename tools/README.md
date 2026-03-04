# Tools

Reusable scripts and code snippets for controlling 3D Slicer programmatically.
Every tool here has been **verified to work** on Slicer 5.10 (linux-amd64) unless noted otherwise.

> **Agents:** load `tools/index.json` first — it is the compact, machine-readable index.
> Find relevant tools by `category` or `tags`, then fetch only the specific script you need.
> Do **not** read all scripts upfront.

When you discover a working pattern, add it here. See `.claude/skills/self-evolution/SKILL.md` for the full process.

---

## Structure

```
tools/
├── index.json             ← machine-readable index (agents start here)
├── README.md              ← human-readable companion (this file)
├── ROADMAP.md             ← development roadmap
├── scene/                 ← MRML scene, node management, transforms
├── volumes/               ← volume loading, resampling, conversion
├── segmentation/          ← segmentation effects, label maps, export
├── visualization/         ← rendering, layout, screenshots, camera
├── io/                    ← file I/O: DICOM, NRRD, NIfTI, STL, OBJ, VTK
├── automation/            ← headless/batch scripts, CLI wrappers
└── snippets/              ← short patterns stored in .md files
```

---

## scene/

| File | Tags | Description |
|------|------|-------------|
| `list-mrml-nodes.py` | mrml, nodes, inspect, debug | List all MRML nodes (index, class, name) in current scene |

## volumes/

| File | Tags | Description |
|------|------|-------------|
| `load-sample-mrhead.py` | volume, load, sample, MRHead | Download MRHead sample volume via SampleData module |

## segmentation/

| File | Tags | Description |
|------|------|-------------|
| *(empty)* | | |

## visualization/

| File | Tags | Description |
|------|------|-------------|
| `enable-volume-rendering.py` | volume rendering, preset, MR-Default, CT-Bone | Enable volume rendering with a named preset |
| `capture-3d-screenshot.py` | screenshot, capture, PNG, 3D view | Capture and save the 3D view widget as PNG |

## io/

| File | Tags | Description |
|------|------|-------------|
| *(empty)* | | |

## automation/

| File | Tags | Description |
|------|------|-------------|
| `run-slicer-script.sh` | launch, headless, batch, CLI | Launch Slicer with a Python script (GUI or headless) |

## snippets/

| File | Contents |
|------|----------|
| *(empty)* | |

---

## Key API Gotchas (Slicer 5.10)

| Wrong | Correct |
|-------|---------|
| `slicer.app.applicationVersion()` | `slicer.app.applicationVersion` (property, no call) |
| `volRenLogic.CreateDefaultVolumeRenderingDisplayNode()` | `volRenLogic.CreateVolumeRenderingDisplayNode()` |
| `volRenLogic.ApplyPreset(displayNode, presetNode)` | `displayNode.GetVolumePropertyNode().Copy(presetNode)` |
| `--python-code` flag | `--python-script <file>` (code flag unreliable) |

---

## Script Header Template

Every standalone `.py` or `.sh` tool must start with this block:

```python
"""
Tool:        <filename>
Category:    <scene|volumes|segmentation|visualization|io|automation>
Tags:        <comma-separated keywords agents will search for>
Description: <one sentence — what it does and what it returns/produces>
Usage:       <how to invoke — Slicer console, --python-script, CLI, etc.>
Version:     1.0
Verified:    YYYY-MM-DD  (Slicer X.Y.Z)
"""
```

## Snippet File Template

Each `snippets/<category>.md` follows this structure:

````markdown
# <Category> Snippets

## <Title>

**When to use:** <trigger condition>
**Tags:** <comma-separated keywords>

```python
# code
```

**Notes:** <gotchas, version caveats>

---
````
