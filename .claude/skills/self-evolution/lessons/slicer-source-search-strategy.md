# Lesson: Searching Slicer Source Code — Start at the Widget Layer

## What happened

**Task:** Find what controls the behavior of Slicer's Python interactor.

**Correct answer:** `CTK/Libs/Scripting/Python/Widgets/ctkPythonConsole.cpp` — the C++ widget that *is* the interactor.

**What I did instead:**
1. Searched `code-index-mcp` for `PythonInteractor` → nothing
2. Found `ctkPythonConsole.cpp/h` via `find_files *Python*Console*` — the correct file
3. **Pivoted away** from it and kept searching
4. Traced the C++ wiring in `qSlicerApplication.cxx` and `qSlicerPythonManager.cxx`
5. Landed on `slicer/slicerqt.py` — a correct but **higher-level** answer (the Python init script, not the widget itself)

## The mistake

Once `find_files` returned `ctkPythonConsole.cpp`, I had the answer. I didn't recognize it because I was pattern-matching on "Python script" instead of "what controls behavior".

In a Qt application, **the widget class IS the behavior**. `ctkPythonConsole` handles:
- Input editing (prompt, history, completion)
- Code execution dispatch
- Output display (stdout/stderr routing)
- Keyboard shortcuts and interaction model

The Python script (`slicerqt.py`) only sets up the *namespace* available in the console — it does not control the console's behavior.

## How to search Slicer source correctly

### Layer model (bottom → top)

```
ctkPythonConsole.cpp        ← widget behavior (input/output/UX)
qSlicerApplication.cxx      ← creates and wires the console to the app
qSlicerPythonManager.cxx    ← executes slicerqt.py at startup
slicer/slicerqt.py          ← populates the Python namespace
~/.slicerrc.py              ← user customization hook
```

### Search strategy

| Question | Where to look | Tool |
|---|---|---|
| "What IS this UI component?" | CTK source (`CTK/Libs/`) | `find_files *<name>*` |
| "How is it wired into Slicer?" | `Slicer/Base/QTGUI/` or `QTApp/` | `grep ctkPythonConsole *.cxx` |
| "What Python runs at startup?" | `qSlicerPythonManager.cxx` line with `executeFile` | grep `executeFile` |
| "What's in the Python namespace?" | `slicer/slicerqt.py`, `slicer/util.py` | code-index or read |
| "User customization hook?" | `slicerqt.py::getSlicerRCFileName()` | already in slicerqt.py |

### Key rule

> When `find_files` returns a `.cpp/.h` file whose name directly matches the concept (e.g., `ctkPythonConsole` for "Python console"), **that is the answer**. Don't keep searching.

## Tool-specific lessons

- `code-index-mcp` + `find_files` — good for locating C++ widget files by name pattern
- `CodeGraphContext` — good for Python-level call graphs; misses C++ → Python calls (e.g., `executeFile`)
- `grep` on `.cxx` files — essential for tracing how C++ components are wired together; neither MCP tool handles C++ call graphs well
- The CTK layer (`source_code/CTK/`) is where Qt widget behavior lives; Slicer only wraps/configures it

## Tags

`slicer`, `ctk`, `ctkPythonConsole`, `python-interactor`, `source-search`, `widget`, `code-navigation`, `MCP`, `code-index`
