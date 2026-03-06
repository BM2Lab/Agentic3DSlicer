"""
Tool:        check-module-registered
Category:    automation
Tags:        module, registration, scripted module, factory, verify, check
Description: Verify that a named scripted module was successfully registered by Slicer's
             factory manager. Prints SUCCESS or FAIL, then quits Slicer.
Usage:       Set MODULE_NAME, then run headless:
             DISPLAY=:1 Slicer --additional-module-paths /path/to/MyModule \
               --no-main-window --python-script check-module-registered.py
Version:     1.0
Verified:    2026-03-05
"""

import slicer

# --- Configure ---
MODULE_NAME = "SATSeg"  # change to target module name
# -----------------

factory = slicer.app.moduleManager().factoryManager()
names = factory.registeredModuleNames()

if MODULE_NAME in names:
    print(f"SUCCESS: {MODULE_NAME} module is registered")
else:
    print(f"FAIL: {MODULE_NAME} not found in registered modules")
    related = [n for n in names if MODULE_NAME.lower() in n.lower()]
    print(f"Related modules: {related}")

slicer.app.quit()
