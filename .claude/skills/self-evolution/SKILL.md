---
name: self-evolution
description: |
  Save reusable 3D Slicer code into the tools/ folder after discovering
  working patterns, debugging solutions, or completing non-trivial tasks.
  Activates after any task that produced a script, snippet, or workflow
  pattern worth reusing — e.g. loading a volume, running headless Slicer,
  manipulating MRML nodes, segmentation, rendering, or file I/O. Keeps the
  project's tool library growing so future tasks start with more leverage.
version: 1.1.0
---

# Self-Evolution Skill

Every time you solve a non-trivial 3D Slicer task, ask yourself:

> **"Would this code help me — or another agent — the next time this comes up?"**

If yes, save it to `tools/`. This is how the project gets smarter over time.

---

## When to Activate

Trigger this skill after you:

- Write a Python script that controls Slicer (headless or GUI)
- Debug an error and find the root cause + fix
- Discover a working pattern for MRML node manipulation
- Figure out a non-obvious Slicer API call
- Build a workflow (e.g. load → segment → export)
- Write a shell command or launcher pattern that works reliably

Do **not** save things that are: one-liners already in the docs, project-specific configs, or code that was never tested and confirmed working.

---

## Tool Discovery (How Agents Find Tools)

**Agents must not read all scripts upfront.** The workflow is:

1. Read `tools/index.json` — compact metadata for every tool (~1–2 KB total)
2. Search by `category` or `tags` to find candidates
3. Fetch only the matched script file(s)

This keeps token cost minimal regardless of library size.

---

## Tool Categories

All tools live under `tools/`. Use the category that best matches the tool's purpose:

| Folder | Contents |
|--------|----------|
| `tools/scene/` | MRML scene creation, node management, transforms |
| `tools/volumes/` | Volume loading, resampling, conversion |
| `tools/segmentation/` | Segmentation effects, label maps, export |
| `tools/visualization/` | Rendering, layout, screenshot, camera control |
| `tools/io/` | File I/O: DICOM, NRRD, NIfTI, STL, OBJ, VTK |
| `tools/automation/` | Headless/batch scripts, CLI wrappers |
| `tools/snippets/` | Short reusable code pieces stored in `.md` files |

Create the subfolder if it does not yet exist.

---

## Two Tool Formats

### Format A — Standalone Script (`.py` or `.sh`)

Use for complete, runnable scripts.

**Naming:** `<verb>-<noun>.py` — lowercase, hyphenated, descriptive.
Examples: `load-nrrd-volume.py`, `run-headless-slicer.sh`, `export-segmentation-stl.py`

**Required header block:**

```python
"""
Tool:        <filename>
Category:    <category>
Tags:        <comma-separated keywords agents will search for>
Description: <one sentence — what it does and what it returns/produces>
Usage:       <how to invoke — Slicer console, --python-script, CLI, etc.>
Version:     1.0
Verified:    YYYY-MM-DD  (Slicer X.Y.Z)
"""
```

**Tags guidance:** include the main action verb, key object names, relevant API class names, and any error message keywords this tool resolves. Aim for 5–10 tags.

### Format B — Snippet Collection (`.md`)

Use for short patterns, API tricks, or multi-language snippets that are
too small for a standalone file but worth preserving.

Store these in `tools/snippets/<category>.md`.

**Structure inside each `.md`:**

````markdown
# <Category> Snippets

## <Short title of snippet>

**When to use:** <one line trigger condition>
**Tags:** <comma-separated keywords>

```python
# code here
```

**Notes:** <any gotchas, version notes, or caveats>

---
````

---

## Steps to Save a Tool

1. **Choose a category** from the table above.
2. **Choose a format** — standalone script if it's self-contained and runnable; snippet if it's a short pattern or API trick.
3. **Write the file** with the required header including `Tags:`.
4. **Update `tools/index.json`** — add a new entry object. This is the primary index.
5. **Update `tools/README.md`** — add a one-line row to the correct section table.
6. **Update `info/project_structure.md`** if new folders were created.

---

## Updating tools/index.json

`tools/index.json` is the primary machine-readable index. Each tool entry:

```json
{
  "id": "<category>/<tool-name-without-extension>",
  "file": "<category>/<filename>",
  "category": "<category>",
  "description": "<one sentence>",
  "tags": ["tag1", "tag2", "tag3"],
  "usage": "<brief invocation note>",
  "slicer_version": "5.10+",
  "verified": "YYYY-MM-DD"
}
```

Add the new entry to the `"tools"` array. Keep the array sorted by category then filename.

---

## Quality Gates

Before saving, confirm:

- [ ] The code was actually **run and verified** (not just written)
- [ ] It would help with a **future task**, not just this exact case
- [ ] It has a **clear trigger condition** (when would someone reach for this?)
- [ ] The header / description is filled in completely
- [ ] `Tags:` field is filled with 5–10 meaningful keywords
- [ ] **No identity leakage** — see rule below

If any gate fails, don't save — or note it as `UNVERIFIED` in the description.

---

## Anonymity Rule

Scripts and documents must not expose the user's identity. Before saving any tool or updating any document, scan for and replace:

| What to strip | Replace with |
|---------------|--------------|
| Absolute paths containing usernames (e.g. `/home/<user>/...`) | Relative paths or `/path/to/project/...` |
| Lab or institution names in paths, comments, or metadata | Generic term or omit |
| Real author names in file headers or comments | Omit, or use `Author: agent` |
| Hostnames, email addresses, or machine-specific config values | Omit or use a placeholder |

**Example — bad:**
```python
SLICER_PATH = "/home/username/myproject/Slicer-5.10.0-linux-amd64/Slicer"
```

**Example — good:**
```python
SLICER_PATH = "/path/to/Slicer-5.10.0-linux-amd64/Slicer"  # set to your local Slicer binary
```

Apply this rule to: script headers, inline comments, example paths, documentation prose, and any default values in function arguments.

---

## Example

After discovering that this pattern reliably loads a NRRD volume headlessly:

```python
import slicer
volumeNode = slicer.util.loadVolume("/path/to/file.nrrd")
```

1. Save as `tools/volumes/load-nrrd-volume.py` with full header + tags
2. Add entry to `tools/index.json`
3. Add row to `tools/README.md` volumes table
4. Done

---

## Lessons

Non-tool-specific experience (bugs, API traps, pitfalls) that don't fit as a
runnable script lives in `.claude/skills/self-evolution/lessons/`.

When you discover something worth remembering that isn't a reusable script —
save a `.md` file there. Use it as a reference before repeating past mistakes.

Current lessons:

| File | Topic |
|------|-------|
| `lessons/slicer-restart-loop-pitfall.md` | `slicer.app.restart()` causes infinite loop when `--python-script` is reused |

---

## Explicit Trigger

You can also manually request self-evolution:

```
/self-evolve
Save what we just built as a tool.
```
