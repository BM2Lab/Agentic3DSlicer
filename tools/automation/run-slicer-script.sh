#!/bin/bash
# Tool:        run-slicer-script.sh
# Category:    automation
# Tags:        launch, headless, batch, shell, automation, CLI, --python-script, no-main-window
# Description: Launch 3D Slicer with a Python script, with or without GUI
# Usage:       ./run-slicer-script.sh <script.py> [--headless]
# Version:     1.0
# Verified:    2026-03-04

SLICER_BIN="/path/to/Slicer-5.10.0-linux-amd64/Slicer"  # set to your local Slicer binary
DISPLAY_VAR=":1"
SCRIPT="$1"
MODE="$2"

if [ -z "$SCRIPT" ]; then
    echo "Usage: $0 <script.py> [--headless]"
    exit 1
fi

if [ "$MODE" = "--headless" ]; then
    # No GUI — script must call sys.exit(0) to terminate
    "$SLICER_BIN" --no-main-window --python-script "$SCRIPT"
else
    # GUI mode — window appears on DISPLAY, script runs after 3s delay via QTimer
    DISPLAY="$DISPLAY_VAR" "$SLICER_BIN" --python-script "$SCRIPT" &
    echo "Slicer GUI launched (PID: $!)"
fi
