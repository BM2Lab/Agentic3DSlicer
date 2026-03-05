# Automation Snippets

## Slicer Restart — Infinite Loop Prevention

**When to use:** Any time a script calls `slicer.app.restart()`.

**Tags:** restart, loop, flag file, install, extension

```python
import os, slicer

FLAG_FILE = "/tmp/slicer_restart_once.flag"

def do_work_then_restart():
    # Guard: post-restart run — skip without restarting again
    if os.path.exists(FLAG_FILE):
        os.remove(FLAG_FILE)
        print("Post-restart: continuing with next phase.")
        return  # ← do NOT call restart() again

    # ... do the work that requires a restart (e.g. install extensions) ...

    # Write flag BEFORE calling restart() — code after restart() never runs
    open(FLAG_FILE, "w").close()
    slicer.app.restart()
```

**Notes:**
- `slicer.app.restart()` re-launches Slicer with the **same `--python-script` arguments**
- Without the flag guard this creates an **infinite restart loop**
- Write the flag *before* calling `restart()` because `restart()` exits immediately
- Delete the flag on re-entry so future independent runs work correctly
- Full reference: `~/.claude/skills/claudeception/resources/slicer-restart-loop-pitfall.md`

---

## Two-Phase Script Pattern (Safer Alternative)

**When to use:** Multi-step workflows where each phase is independent.

**Tags:** phase, two-phase, install, workflow, automation

```bash
# Phase 1 — install/setup, then quit (not restart)
DISPLAY=:1 ./Slicer --python-script phase1_install.py

# Phase 2 — run after setup, separate script
DISPLAY=:1 ./Slicer --python-script phase2_work.py
```

```python
# In phase1_install.py — quit instead of restart
# ... do setup ...
slicer.app.quit()  # exits cleanly, does NOT re-run the script
```

**Notes:**
- Simpler than flag file — no shared state risk
- Requires external orchestrator (shell script or CI) to run phases in sequence
- Use `slicer.app.quit()` not `restart()` for clean exit

---

## extensionsManagerModel — GUI Only

**When to use:** Before calling any extensionsManagerModel method.

**Tags:** extension, headless, GUI, block, hang

```python
# CHECK: extensionsManagerModel() hangs forever in headless mode
# Only call it when running with a display (GUI mode)
import slicer
# WRONG — blocks forever:
# em = slicer.app.extensionsManagerModel()   # in --no-main-window mode

# RIGHT — only in GUI session:
if slicer.app.mainWindow():
    em = slicer.app.extensionsManagerModel()
```

**Notes:**
- `--no-main-window` mode: `extensionsManagerModel()` never returns
- Always guard with `slicer.app.mainWindow()` check or run only in GUI mode
