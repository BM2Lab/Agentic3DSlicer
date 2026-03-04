# 3D Slicer Resources

## Official Website
- **Homepage:** https://slicer.org — downloads, news, overview

## Documentation
- **Main docs (ReadTheDocs):** https://slicer.readthedocs.io/en/latest
  - User Guide: https://slicer.readthedocs.io/en/latest/user_guide/getting_started.html
  - Developer Guide: https://slicer.readthedocs.io/en/latest/developer_guide/index.html
  - Python FAQ: https://slicer.readthedocs.io/en/latest/developer_guide/python_faq.html
  - Script Repository (code examples): https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html
  - Extensions guide: https://slicer.readthedocs.io/en/latest/developer_guide/extensions.html
- **Legacy Wiki:** https://www.slicer.org/wiki/Main_Page (Slicer ≤ 4.10)

## API References
- **C++ / MRML / VTK API (Doxygen):** https://apidocs.slicer.org/master — full class reference for `vtkMRMLScene`, `vtkMRMLNode`, `vtkMRMLSliceNode`, etc.
- **Python API:** exposed via the `slicer` package inside the bundled Python interpreter; key sub-modules:
  - `slicer` — top-level namespace (access `slicer.app`, `slicer.mrmlScene`, `slicer.modules`)
  - `slicer.util` — helper functions for loading, saving, node management
  - `slicer.ScriptedLoadableModule` — base class for scripted modules
  - `slicer.cli` — command-line interface wrappers
  - `slicer.logic`, `slicer.testing`

## Source Code
- **Main repo (C++ / Python / CMake):** https://github.com/Slicer/Slicer
- **Scripted modules (Python examples):** https://github.com/Slicer/Slicer/tree/main/Modules/Scripted
- **Extensions index:** https://github.com/Slicer/ExtensionsIndex
- **Slicer Docker:** https://github.com/Slicer/SlicerDocker
- **GitHub wiki:** https://github.com/Slicer/Slicer/wiki

## Running Python Scripts in Slicer
```bash
# Run a script non-interactively
./Slicer --python-script /path/to/script.py

# Run inline Python code
./Slicer --python-code "import slicer; print(slicer.app)"

# Startup file (auto-loaded on launch)
~/.slicerrc.py
```

## Community & Training
- **Discourse forum:** https://discourse.slicer.org — primary Q&A and discussion
- **Training compendium:** https://training.slicer.org — step-by-step tutorials with sample data (multiple languages)
- **Training wiki (older versions):** https://www.slicer.org/wiki/Training

## Key Libraries (underlying stack)
| Library | Role |
|---------|------|
| VTK | 3D rendering and visualization pipeline |
| ITK | Image processing and registration |
| MRML | Scene graph: nodes for volumes, models, markups, transforms |
| CTK | Common Toolkit — Qt widgets and DICOM support |
| Qt 5 | GUI framework |
