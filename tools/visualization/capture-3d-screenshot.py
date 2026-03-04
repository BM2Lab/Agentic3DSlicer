"""
Tool:        capture-3d-screenshot.py
Category:    visualization
Tags:        screenshot, capture, render, 3D view, PNG, image, save, Qt grab
Description: Capture a screenshot of the 3D view widget and save to disk
Usage:       Set `output_path` before running, or call capture_3d_screenshot()
Version:     1.0
Verified:    2026-03-04  (Slicer 5.10.0)

Notes:
- Uses Qt widget.grab() on the threeDWidget — captures the full 3D panel including toolbar
- Call forceRenderAllViews() + processEvents() + sleep(2) before grab() for complete render
- Output is a PNG file
"""
import slicer
import time

def capture_3d_screenshot(output_path="/tmp/3d_view.png", widget_index=0):
    layoutMgr = slicer.app.layoutManager()

    # Ensure rendering is complete before capture
    slicer.util.forceRenderAllViews()
    slicer.app.processEvents()
    time.sleep(2)
    slicer.util.forceRenderAllViews()
    slicer.app.processEvents()

    widget = layoutMgr.threeDWidget(widget_index)
    pixmap = widget.grab()
    pixmap.save(output_path)
    print(f"Screenshot saved: {output_path}")
    return output_path


# Example usage:
# capture_3d_screenshot("/tmp/my_render.png")
