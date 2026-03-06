# Agentic 3D Slicer

> **Work in progress.** This project is under active development.

A growing library of reusable tools and infrastructure that lets LLM agents control [3D Slicer](https://slicer.org) programmatically — the same way a human would.

## What it does

Agents can use this library to load medical image data, manipulate the scene, run segmentation, render volumes, capture screenshots, and automate workflows — all through 3D Slicer's Python API.

## Milestones

### M1 — SAT Segmentation (2026-03-06)

An LLM agent built a full text-prompted segmentation pipeline from scratch — no human wrote any of the integration code.

The pipeline: a Flask inference server wraps [SAT-Nano](https://github.com/zhaoziheng/SAT) in a separate Python environment; a 3D Slicer scripted module sends volumes over HTTP and visualises the returned masks as named, coloured segments. The agent debugged PyTorch compatibility with RTX 5090 (sm_120 Blackwell), patched DDP and NCCL for single-GPU inference, and produced a working module across five implementation phases.

![CT abdomen segmentation — liver, spleen, left kidney, right kidney](modules/Segmentation/agent/eval_ct_abdomen.png)

*CT abdominal organs segmented via text prompt (`liver, spleen, left kidney, right kidney`). Four well-separated, coloured meshes rendered directly in Slicer's 3D view.*

→ Full details: [`modules/Segmentation/README.md`](modules/Segmentation/README.md)

---

## Structure

```
tools/          reusable Python scripts and shell tools
  index.json    machine-readable tool index (agents start here)
  ROADMAP.md    infrastructure plan
info/           project notes, goals, resources
.claude/        agent skills and configuration
```

## Requirements

- [3D Slicer 5.10+](https://download.slicer.org) installed locally
- Linux (tested on Ubuntu with Slicer 5.10.0-linux-amd64)

## Using the tools

Run a script inside Slicer:

```bash
./Slicer-5.10.0-linux-amd64/Slicer --python-script tools/volumes/load-sample-mrhead.py
```

Or headlessly (no GUI):

```bash
./Slicer-5.10.0-linux-amd64/Slicer --no-main-window --python-script tools/scene/list-mrml-nodes.py
```

## Resources

- [3D Slicer documentation](https://slicer.readthedocs.io/en/latest)
- [Script repository](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html)
- [Slicer Python API](https://apidocs.slicer.org/master)
- [Community forum](https://discourse.slicer.org)

## License

TBD
