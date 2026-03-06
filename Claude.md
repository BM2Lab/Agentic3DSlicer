# Agentic 3D Slicer Builder

# Philosophy

You are tasked to build 3D Slicer infrastructure for LLM agent like you so that you can manipulate 3D Slicer as a human does.

# Information

See [project_structure](./info/project_structure.md) for last stored project hierachy. Remember to update it so each initialization.

See [resources](./info/resources.md) for 3D Slicer's online documentations. Remember to update it if you find something else.

# Self-evolution

After completing any non-trivial 3D Slicer task, save reusable code to `tools/` so the project accumulates working knowledge over time.

**Skill:** `.claude/skills/self-evolution/SKILL.md` — read it for the full process.

**Finding tools (agents):** load `tools/index.json` first — it is the compact machine-readable index (~1–2 KB). Search by `category` or `tags`, then fetch only the specific script needed. Do not read all scripts upfront.

**Quick rules:**
1. Verified and reusable → save it. One-liners already in the docs → skip.
2. Choose a format:
   - **Standalone script** (`.py` / `.sh`) for complete, runnable tools → `tools/<category>/<verb>-<noun>.py`
   - **Snippet** for short patterns or API tricks → `tools/snippets/<category>.md`
3. Every script needs a standard header with `Tool`, `Category`, `Tags`, `Description`, `Usage`, `Version`, `Verified`.
4. Always update **both** `tools/index.json` (primary) and `tools/README.md` (human table) after adding a tool.
5. No identity leakage — no absolute paths with usernames, no lab names, no hostnames.

**Tool categories:**

| Folder | Purpose |
|--------|---------|
| `tools/scene/` | MRML scene, node management, transforms |
| `tools/volumes/` | Volume loading, resampling, conversion |
| `tools/segmentation/` | Segmentation effects, label maps, export |
| `tools/visualization/` | Rendering, layout, screenshots, camera |
| `tools/io/` | File I/O — DICOM, NRRD, NIfTI, STL, OBJ |
| `tools/automation/` | Headless/batch scripts, CLI wrappers |
| `tools/snippets/` | Short code patterns in `.md` files |

See `tools/index.json` for the full tool index and `tools/ROADMAP.md` for the infrastructure plan.

## Lessons (Accumulated Knowledge)

**At the start of every task, read `.claude/skills/self-evolution/index.json`.** It is a compact file (~1 KB) listing all known pitfalls and hard-won lessons. Reading it costs almost nothing and prevents repeating past mistakes.

When you **add a new lesson**:
1. Save `.md` to `.claude/skills/self-evolution/lessons/`
2. Add an entry to `.claude/skills/self-evolution/index.json`
3. If the lesson belongs to a sub-project that has an `agent/` subfolder, **also copy the file there** — long tasks lose global context, but a local copy in `agent/` stays discoverable:
   ```bash
   cp .claude/skills/self-evolution/lessons/<lesson>.md modules/<Module>/agent/<lesson>.md
   ```

# User inquery
The user will frequently ask you to achieve certain functions during which you can look into [goal](./info/goal.md) to review and update the goals. That can remind you of the previous attempt and capabilities.