# Segmentation Module — Goals

## Vision

Embed SAT (Segment Anything in 3D — universal medical image segmentation via text prompts)
into 3D Slicer as a scripted module, using a remote inference server architecture.

## Objectives

| # | Goal | Status |
|---|------|--------|
| 1 | Build a minimal Python scripted module and load it into Slicer | Done ✓ |
| 2 | Set up SAT model environment and run inference on this machine | Planned |
| 3 | Wrap SAT inference in a lightweight HTTP server | Planned |
| 4 | Build Slicer client module that sends volumes and receives segmentation masks | Planned |
| 5 | Polish UI: text prompt input, segment editor integration, 3D visualization | Planned |

## References

- SAT model: https://github.com/zhaoziheng/SAT
- Architecture inspiration: https://github.com/coendevente/SlicerNNInteractive
