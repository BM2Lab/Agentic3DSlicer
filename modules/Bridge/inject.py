"""
inject.py — Send a single action to a running Slicer session.

Usage:
  python3 inject.py <qualified_action> [key=value ...]
  python3 inject.py <namespace> <action> [key=value ...]

Examples:
  python3 inject.py volume.load_sample_mrhead
  python3 inject.py volume.get_volume_info node_id=vtkMRMLScalarVolumeNode1
  python3 inject.py markup.create_point_list name=MyPoints
  python3 inject.py markup.add_control_point node_id=vtkMRMLMarkupsFiducialNode1 ras=[10,-5,3] label=P1
  python3 inject.py io.list_loaded_nodes
  python3 inject.py io.clear_scene

  # Shorthand (namespace + action as two args):
  python3 inject.py volume load_sample_mrhead
  python3 inject.py io list_loaded_nodes

  # List available actions:
  python3 inject.py --list
  python3 inject.py --list volume
"""
import ast
import json
import socket
import sys
import uuid
from pathlib import Path

SOCK_PATH = "/tmp/slicer_agent.sock"
sys.path.insert(0, str(Path(__file__).parent))

import slicer_use.actions  # noqa: E402  — triggers all registrations
from slicer_use.controller.service import controller  # noqa: E402


def parse_kwargs(args):
    kwargs = {}
    for a in args:
        if "=" not in a:
            print(f"  skip unparseable arg: {a!r}")
            continue
        k, _, v = a.partition("=")
        try:
            kwargs[k] = ast.literal_eval(v)
        except Exception:
            kwargs[k] = v
    return kwargs


def rpc(code: str) -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(SOCK_PATH)
    except FileNotFoundError:
        print("ERROR: No Slicer session found. Run start_slicer.py first.")
        sys.exit(1)
    req = json.dumps({"id": str(uuid.uuid4()), "code": code}).encode() + b"\n"
    s.sendall(req)
    buf = b""
    while b"\n" not in buf:
        chunk = s.recv(65536)
        if not chunk:
            print("ERROR: Socket closed unexpectedly.")
            sys.exit(1)
        buf += chunk
    s.close()
    return json.loads(buf.split(b"\n", 1)[0])


def print_list(namespace_filter: str | None = None):
    """Print available actions grouped by namespace."""
    schemas = controller.schemas(depth=1)
    for ns_entry in schemas:
        ns = ns_entry["namespace"]
        if namespace_filter and ns != namespace_filter:
            continue
        print(f"\n  {ns}  — {ns_entry['description']}")
        for a in ns_entry["actions"]:
            print(f"    {a['name']:40s} {a['description']}")
    if namespace_filter and not any(
        e["namespace"] == namespace_filter for e in schemas
    ):
        print(f"  Unknown namespace {namespace_filter!r}.")
        print(f"  Available: {controller.namespace_names}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    if sys.argv[1] == "--list":
        ns_filter = sys.argv[2] if len(sys.argv) > 2 else None
        print_list(ns_filter)
        sys.exit(0)

    # Parse action name: either "ns.action" or "ns action"
    first = sys.argv[1]
    if "." in first:
        action_name = first
        rest = sys.argv[2:]
    elif len(sys.argv) >= 3 and "=" not in sys.argv[2]:
        action_name = f"{first}.{sys.argv[2]}"
        rest = sys.argv[3:]
    else:
        action_name = first
        rest = sys.argv[2:]

    kwargs = parse_kwargs(rest)

    # Verify action exists
    entry = controller._actions.get(action_name)
    if entry is None:
        matches = [k for k in controller._actions if k.endswith(f".{action_name}")]
        if len(matches) == 1:
            action_name = matches[0]
            entry = controller._actions[action_name]
        elif len(matches) > 1:
            print(f"Ambiguous action {action_name!r}. Matches: {matches}")
            sys.exit(1)
        else:
            print(f"Unknown action: {action_name!r}")
            print(f"Run: python3 inject.py --list")
            sys.exit(1)

    import asyncio

    class _SyncSession:
        async def run_checked(self, code):
            resp = rpc(code)
            if resp.get("stdout") and resp["stdout"].strip():
                print(f"[slicer] {resp['stdout'].strip()}")
            if resp.get("error"):
                raise RuntimeError(f"Slicer error:\n{resp['error']}")
            return resp

    async def _run():
        session = _SyncSession()
        return await entry["fn"](session, **kwargs)

    kw_str = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
    print(f"→ {action_name}({kw_str})")
    try:
        result = asyncio.run(_run())
        print(f"✓ {result}")
    except Exception as e:
        print(f"✗ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
