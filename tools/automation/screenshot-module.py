"""
Tool:        screenshot-module
Category:    automation
Tags:        screenshot, module, UI, verify, render, PNG, grab
Description: Switch to a named Slicer module and capture the main window as a PNG.
             Useful for verifying that a scripted module's UI renders correctly.
Usage:       Set MODULE_NAME and OUTPUT_PATH, then run with GUI:
             DISPLAY=:1 Slicer --additional-module-paths /path/to/Module \
               --python-script screenshot-module.py
Version:     1.0
Verified:    2026-03-05
"""

import slicer, qt

# --- Configure ---
MODULE_NAME = "SATSeg"
OUTPUT_PATH = "/tmp/slicer_module_screenshot.png"
# -----------------

slicer.util.selectModule(MODULE_NAME)
slicer.app.processEvents()

# Brief pause for rendering
qt.QTimer.singleShot(2000, lambda: None)
slicer.app.processEvents()

mainWindow = slicer.util.mainWindow()
pixmap = mainWindow.grab()
pixmap.save(OUTPUT_PATH)
print(f"Screenshot saved to {OUTPUT_PATH}")

slicer.app.quit()
