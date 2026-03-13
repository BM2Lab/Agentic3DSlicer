"""
fetch_registry.py — Export the Slicer action registry as JSON.

Run this script to produce a machine-readable registry file that LLM agents
can read to discover available Slicer actions.

Usage:
    python3 fetch_registry.py                       # full detail → registry.json
    python3 fetch_registry.py --depth 0             # namespace names only (cheapest)
    python3 fetch_registry.py --depth 1             # names + descriptions, no params
    python3 fetch_registry.py --depth -1            # full schemas (default)
    python3 fetch_registry.py --output /tmp/reg.json

Depth levels:
    0   namespace names + descriptions + action_count  (~20 lines)
    1   namespaces with action name + one-line description  (~80 lines)
   -1   full schemas including parameter details  (~300+ lines)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import slicer_use.actions  # noqa: E402  — triggers all @ns.action registrations
from slicer_use.controller.service import controller  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Export the Slicer action registry as JSON"
    )
    parser.add_argument(
        "--depth", type=int, default=-1,
        help="0=namespaces only, 1=names+desc, -1=full (default: -1)"
    )
    parser.add_argument(
        "--output", type=str, default="registry.json",
        help="Output file path (default: registry.json)"
    )
    args = parser.parse_args()

    schemas = controller.schemas(depth=args.depth)
    out = Path(args.output)
    out.write_text(json.dumps(schemas, indent=2) + "\n")

    total_actions = len(controller.names)
    total_ns = len(controller.namespace_names)
    print(
        f"Registry written to {out}  "
        f"(depth={args.depth}, {total_ns} namespaces, {total_actions} actions)"
    )


if __name__ == "__main__":
    main()
