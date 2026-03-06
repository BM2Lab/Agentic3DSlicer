# Slicer Automation Patterns

**Category:** Agentic 3D Slicer — Automation
**Severity:** High — missing these causes hangs, broken registration, and infinite loops
**Discovered:** 2026-03-05

---

## Restart Loop Prevention

`slicer.app.restart()` re-launches Slicer with the **exact same `--python-script` argument**, causing an infinite restart loop unless guarded.

**Fix:** Write a flag file **before** calling `restart()`, delete it on re-entry.

```python
import os, slicer

FLAG_FILE = "/tmp/slicer_restart_once.flag"

def do_work_then_restart():
    if os.path.exists(FLAG_FILE):
        os.remove(FLAG_FILE)
        print("Post-restart: continuing with next phase.")
        return  # ← do NOT restart again

    # ... do the work that requires a restart ...

    open(FLAG_FILE, "w").close()   # write BEFORE restart — code after never runs
    slicer.app.restart()
```

See full detail: `lessons/slicer-restart-loop-pitfall.md`

---

## Two-Phase Script Pattern (Safer Alternative to restart)

Split long automation into two independent scripts run by an external shell orchestrator. Avoids shared state and restart-loop risk entirely.

```bash
# Phase 1 — install/setup, then quit cleanly
DISPLAY=:1 ./Slicer --python-script phase1_install.py

# Phase 2 — run after setup
DISPLAY=:1 ./Slicer --python-script phase2_work.py
```

```python
# phase1_install.py — quit instead of restart
# ... do setup ...
slicer.app.quit()   # exits cleanly; does NOT re-run the script
```

**Notes:**
- `slicer.app.quit()` does not re-invoke the script; `slicer.app.restart()` does
- Use `quit()` for clean exit when next step is controlled by an external orchestrator

---

## Permanently Register a Module (revisionUserSettings)

**Problem:** `--additional-module-paths` must be repeated on every launch.  
**Fix:** Write the path once to `revisionUserSettings()` and Slicer loads it on every startup.

```python
import slicer

MODULE_PATH = "/absolute/path/to/MyModule"  # folder containing MyModule.py

# IMPORTANT: revisionUserSettings(), NOT userSettings()
# Slicer reads Modules/AdditionalPaths from the revision-specific .ini file
settings = slicer.app.revisionUserSettings()
# File: <slicer_bundle>/slicer.org/Slicer-<revision>.ini

key = "Modules/AdditionalPaths"
existing = settings.value(key)
if not existing:
    existing = []
elif isinstance(existing, str):
    existing = [existing]
else:
    existing = list(existing)

if MODULE_PATH not in existing:
    existing.append(MODULE_PATH)
    settings.setValue(key, existing)
    settings.sync()
    print("Registered:", MODULE_PATH)
```

**Notes:**
- `userSettings()` → `~/.config/slicer.org/Slicer.ini` — Slicer does **not** read module paths from here
- `revisionUserSettings()` → `<slicer_bundle>/slicer.org/Slicer-<revision>.ini` — where `Modules/AdditionalPaths` is actually read
- `settings.value()` may return `None`, a `str`, or a `tuple` — always normalize to `list` before appending
- Run once headless (`--no-main-window --python-script`), then plain `Slicer` picks up the path on every launch

---

## Register a Scripted Module via --additional-module-paths

**When to use:** Loading a custom scripted module into Slicer without modifying the app bundle.

```bash
# Module folder must match the .py filename (e.g. SATSeg/SATSeg.py)
DISPLAY=:1 Slicer --additional-module-paths /path/to/SATSeg

# Headless check (verify registration without opening full GUI):
DISPLAY=:1 Slicer --additional-module-paths /path/to/SATSeg \
  --no-main-window --python-script check-module-registered.py
```

```python
# Inside Slicer — check registration via factory manager
factory = slicer.app.moduleManager().factoryManager()
names = factory.registeredModuleNames()   # returns list of strings
print("SATSeg" in names)                  # True if registered
```

**Notes:**
- Folder name and `.py` filename must match the module class name exactly (case-sensitive)
- `registeredModuleCount()` does NOT exist — use `registeredModuleNames()` (Slicer 5.10)
- `--no-main-window` is fine for registration checks; module widget won't render but the factory runs
- For UI screenshot verification, run without `--no-main-window` and use `slicer.util.mainWindow().grab()`

---

## extensionsManagerModel — GUI Mode Only

`extensionsManagerModel()` **hangs forever** in `--no-main-window` (headless) mode. Always guard before calling.

```python
import slicer

# WRONG — blocks forever in headless:
# em = slicer.app.extensionsManagerModel()

# RIGHT — only call in GUI session:
if slicer.app.mainWindow():
    em = slicer.app.extensionsManagerModel()
```

**Notes:**
- `--no-main-window` mode: `extensionsManagerModel()` never returns
- Use `slicer.app.mainWindow()` as a reliable GUI-vs-headless guard

---

## Rules Summary

| Rule | Reason |
|------|--------|
| Never call `restart()` without a flag file guard | Infinite loop risk |
| Write flag before `restart()`, never after | `restart()` exits the process immediately |
| Use `revisionUserSettings()` for persistent module paths | `userSettings()` is ignored for `Modules/AdditionalPaths` |
| Normalize `settings.value()` to list before appending | May return `None`, `str`, or `tuple` |
| Guard `extensionsManagerModel()` with `mainWindow()` check | Hangs in headless mode |
| `registeredModuleNames()` not `registeredModuleCount()` | The count method doesn't exist in Slicer 5.10 |

---

## Related

- `lessons/slicer-restart-loop-pitfall.md` — full detail on restart loop
- `tools/automation/install-extension.py` — uses flag file guard
- `tools/automation/check-module-registered.py` — headless module registration check
- `tools/automation/run-slicer-script.sh` — two-phase launch wrapper
