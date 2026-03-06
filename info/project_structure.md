# Project Structure
```
Agentic3DSlicer/
├── .claude/                    # Claude/IDE config 
├── tools/                      # Project tools 
├── modules/                    # External packages and projects 
├── Claude.md                   # This file — project context for the agent
└── Slicer-5.10.0-linux-amd64/  # 3D Slicer 5.10 installation
    ├── bin/                    # Executables and bundled Python (slicer, qt, ctk, etc.)
    ├── lib/                    # Slicer libs, qt-loadable-modules, qt-scripted-modules, cmake
    ├── libexec/                # Slicer-5.10 runtime
    ├── resources/              # Slicer resources
    ├── share/                  # QtTranslations, Slicer-5.10 (Wizard, qt-loadable-modules), ITK, doc
    └── slicer.org/             # Extensions-34045
```