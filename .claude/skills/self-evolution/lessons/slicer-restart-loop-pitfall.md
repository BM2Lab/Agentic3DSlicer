# Slicer Restart Loop Pitfall

**Category:** Agentic 3D Slicer — Automation
**Severity:** High — causes infinite process spawning
**Discovered:** 2026-03-04

---

## The Problem

`slicer.app.restart()` re-launches Slicer with the **exact same command-line arguments**, including `--python-script <file>`.

If a script calls `restart()` unconditionally (e.g. "already installed → restart to activate"), it creates an **infinite restart loop**:

```
Launch Slicer --python-script install.py
  → script runs, extensions already installed
  → calls slicer.app.restart()
  → Slicer relaunches with --python-script install.py
  → script runs again, extensions still installed
  → calls slicer.app.restart()
  → ... forever
```

This silently spawns dozens of Slicer processes, consuming RAM and CPU until the machine is killed or crashes.

---

## The Fix: Flag File Guard

Write a flag file **before** calling `restart()`. On the next launch, detect the flag, delete it, and return early without restarting again.

```python
import os, slicer, qt

FLAG_FILE = "/tmp/slicer_ext_install_done.flag"

def install():
    # Guard: post-restart run — just exit cleanly
    if os.path.exists(FLAG_FILE):
        os.remove(FLAG_FILE)
        print("Post-restart: extensions loaded. Done.")
        return  # ← critical: do NOT restart again

    # ... do installation work ...

    # Write flag BEFORE calling restart
    open(FLAG_FILE, "w").close()
    slicer.app.restart()
```

**Why write the flag before restart (not after)?**
`slicer.app.restart()` exits the current process immediately. Any code after it never runs.

---

## Alternative: `slicer.app.quit()` + Manual Relaunch

If you don't need a seamless automated restart, use `slicer.app.quit()` instead and relaunch with a different script (Phase 2):

```python
# Phase 1 — install only, then quit
slicer.app.quit()

# Phase 2 — separate script, launched manually or by orchestrator
# DISPLAY=:1 Slicer --python-script phase2_work.py
```

This is cleaner for multi-phase automation because each phase is an independent script with no shared state risk.

---

## Rules to Follow

| Rule | Reason |
|------|--------|
| Never call `restart()` without a flag file guard | Infinite loop risk |
| Write flag file **before** `restart()`, never after | `restart()` exits immediately |
| Delete the flag on the guarded re-entry | Clean up, and allow future re-runs |
| For multi-phase workflows, prefer `quit()` + separate scripts | Simpler, no shared state |
| Never use `restart()` in headless scripts | `extensionsManagerModel()` blocks headless anyway |

---

## Detection

If Slicer is spawning endlessly, kill all instances:

```bash
pkill -f SlicerApp-real
```

Then check for and remove any stale flag files before re-running.

---

## Related

- `tools/automation/install-extension.py` — uses flag file guard (v1.1+)
- `tools/automation/run-slicer-script.sh` — two-phase launch wrapper
