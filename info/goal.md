# Project Goals

## Current Task List

| # | Goal | Status |
|---|------|--------|
| 0 | Access and list MRML node information from a running Slicer scene | Done ✓ |
| 1 | Download sample head data (MRHead) from Slicer's built-in SampleData module | Done ✓ |
| 2 | Open the Volume Rendering module and toggle visualization on the loaded volume | Done ✓ |
| 3 | Capture a screenshot of the 3D window and save it to disk | Done ✓ |

## Notes
- Slicer binary: `Slicer-5.10.0-linux-amd64/Slicer`
- Display: `:1`
- Headless test confirmed working with `--no-main-window --python-script`
- GUI launch confirmed working with `DISPLAY=:1 Slicer &`
