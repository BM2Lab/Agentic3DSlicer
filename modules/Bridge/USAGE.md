# Bridge Module — Usage Guide

## Overview

The Bridge module lets an LLM agent (or human operator) control a running 3D Slicer instance over a Unix socket. Actions are organised into **namespaced groups** registered in a single global controller.

```
LLM agent / human CLI
       │
       ▼
  inject.py  or  host Python process
       │
       ▼
  SlicerController  (global registry of all actions)
       │
       ▼
  SlicerSession  (Unix socket RPC to Slicer subprocess)
       │
       ▼
  3D Slicer  (bootstrap.py runs inside, listens on socket)
```

---

## 1. Start Slicer

```bash
cd modules/Bridge
python3 start_slicer.py          # launches Slicer with bootstrap, waits for socket
```

Leave this running. The socket defaults to `/tmp/slicer_agent.sock`.

---

## 2. Discover available actions

### Option A — CLI listing

```bash
python3 inject.py --list                   # all namespaces + actions
python3 inject.py --list segmentation      # actions in one namespace
```

### Option B — Generate a registry file

```bash
python3 fetch_registry.py                          # full detail → registry.json
python3 fetch_registry.py --depth 0                # cheapest: namespace summaries
python3 fetch_registry.py --depth 1                # names + descriptions, no params
python3 fetch_registry.py --depth -1               # full schemas with params (default)
python3 fetch_registry.py --output /tmp/reg.json   # custom output path
```

The output `registry.json` is a machine-readable file an LLM agent can read to know what tools are available.

### Depth levels explained

| Depth | What's included | Typical size | When to use |
|-------|----------------|-------------|-------------|
| `0` | Namespace name, description, action count | ~20 lines | Agent deciding which area to explore |
| `1` | + action names and one-line descriptions | ~80 lines | Agent choosing which action to call |
| `-1` | + full parameter schemas (name, type, default) | ~300+ lines | Agent constructing the actual call |

**Recommended workflow for a token-conscious agent:**

1. Read `registry.json` at depth `0` → pick relevant namespace(s)
2. Re-run at depth `1` for those namespace(s) → pick the action
3. Re-run at depth `-1` for that specific action → get the parameter schema
4. Call the action

Or just use depth `-1` if token budget is not a concern (~300 lines for 52 actions).

---

## 3. Call actions

### From the CLI (human-in-the-loop)

```bash
# Qualified name (namespace.action):
python3 inject.py volume.load_sample_mrhead
python3 inject.py volume.get_volume_info node_id=vtkMRMLScalarVolumeNode1

# Two-arg shorthand (namespace action):
python3 inject.py markup create_point_list name=MyPoints
python3 inject.py markup add_control_point node_id=vtkMRMLMarkupsFiducialNode1 ras=[10,-5,3]

# Unqualified name (works if globally unique):
python3 inject.py clear_scene
```

### From Python (LLM host process)

```python
from slicer_use.controller.service import controller
import slicer_use.actions  # triggers all registrations

from slicer_use.slicer.session import SlicerSession

async def main():
    async with SlicerSession(slicer_bin="/path/to/Slicer") as session:
        # By qualified name
        result = await controller.call("volume.load_sample_mrhead", session)
        print(result.value)  # {"id": "vtkMRMLScalarVolumeNode1", "name": "MRHead"}

        # By short name (if unique)
        result = await controller.call("clear_scene", session)
```

---

## 4. Namespace reference

| Namespace | Description | Actions |
|-----------|-------------|---------|
| `crop` | Volume cropping to ROI or auto-detected bounding box | 2 |
| `histogram` | Intensity histogram, point sampling, Otsu threshold, masked stats | 4 |
| `io` | DICOM import, scene save/clear, generic node listing | 4 |
| `markup` | Fiducial points, ROIs, markup load/save | 7 |
| `model` | 3D surface models: load, export, stats, display | 5 |
| `scene` | MRML scene inspection and snapshots | 2 |
| `segment_editor` | Headless-safe segment editing: islands, smooth, threshold, margin, hollow | 5 |
| `segmentation` | Create, threshold, export, and import segmentations | 7 |
| `transform` | Linear transforms: create, apply, harden, read, load | 5 |
| `visualization` | Layout, screenshots, volume rendering, camera rotation | 4 |
| `volume` | Volume loading, resampling, conversion, export | 8 |

**Total: 11 namespaces, 53 actions**

---

## 5. Adding a new action

1. Choose or create a file in `slicer_use/actions/` (one file per namespace).

2. Register actions using the global controller:

   ```python
   from ..controller.service import controller
   from ..slicer.session import SlicerSession

   ns = controller.namespace("my_namespace", "Short description of this group")

   @ns.action("One-line description of what this does")
   async def my_action(session: SlicerSession, param1: str, param2: int = 10) -> dict:
       resp = await session.run_checked(f"""
   import slicer
   # ... Slicer Python code ...
   __result__ = {{"key": "value"}}
   """)
       return resp["result"]
   ```

3. If you created a new file, add it to `slicer_use/actions/__init__.py`:

   ```python
   from . import my_namespace  # noqa: F401
   ```

4. Re-run `python3 fetch_registry.py` to update `registry.json`.

That's it — no hardcoded maps, no separate registration step. The `@ns.action` decorator does all the work at import time.

---

## 6. Architecture notes

- **Single global controller:** `slicer_use/controller/service.py` exports a module-level `controller` singleton. All action modules import it and register into the same registry.

- **Namespace = category prefix:** Actions are stored as `"namespace.function_name"` in the controller. `call()` accepts both qualified and short names (short names resolved by searching all namespaces; error if ambiguous).

- **inject.py is just a thin CLI wrapper:** It imports all actions (triggering registration), resolves the action name against the controller, creates a minimal sync session over the Unix socket, and calls the action once.

- **fetch_registry.py is for agents:** It writes a JSON file that an LLM agent can `cat` or read to discover tools without importing Python.

- **SlicerSession is the RPC transport:** Each session owns a Slicer subprocess + Unix socket. Actions are async functions that send Python code strings to Slicer and parse the response. Multiple sessions = multiple Slicer instances.
