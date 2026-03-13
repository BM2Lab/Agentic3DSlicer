"""
SlicerController — hierarchical namespace action registry.

All action modules register against a single global `controller` instance.
Each module creates a namespace via `controller.namespace(...)` and decorates
async functions with `@ns.action(...)`.

Usage (in an action module):

    from ..controller.service import controller
    ns = controller.namespace("volume", "Volume loading, resampling, conversion")

    @ns.action("Load a volume file into the scene")
    async def load_volume(session: SlicerSession, path: str) -> dict:
        ...

Usage (in host / LLM integration):

    import slicer_use.actions          # triggers all registrations
    from slicer_use.controller.service import controller

    schemas  = controller.schemas(depth=1)          # summaries for the LLM
    result   = await controller.call("volume.load_volume", session, path="/tmp/t1.nii.gz")

Depth parameter for schemas():
    0   namespace names + descriptions only (cheapest)
    1   namespaces with action names + one-line descriptions (no parameters)
   -1   full schemas with parameter details (default, most expensive)
"""
from __future__ import annotations

import inspect
from typing import Any, Callable


class ActionResult:
    """Wraps the return value of an action for uniform handling."""

    def __init__(self, value: Any, error: str | None = None):
        self.value = value
        self.error = error
        self.ok = error is None

    def __repr__(self):
        if self.error:
            return f"ActionResult(error={self.error!r})"
        return f"ActionResult(value={self.value!r})"


class _Namespace:
    """Proxy returned by controller.namespace(); registers actions under a prefix."""

    def __init__(self, ctrl: SlicerController, name: str):
        self._ctrl = ctrl
        self._name = name

    def action(self, description: str) -> Callable:
        """Decorator — registers the function under this namespace."""
        def decorator(fn: Callable) -> Callable:
            self._ctrl._register(self._name, fn, description)
            return fn
        return decorator


class SlicerController:

    def __init__(self):
        self._namespaces: dict[str, str] = {}   # name → description
        self._actions: dict[str, dict] = {}      # "ns.fn_name" → entry

    # ── Registration ──────────────────────────────────────────────────────

    def namespace(self, name: str, description: str = "") -> _Namespace:
        """Create (or update) a namespace and return a decorator proxy."""
        self._namespaces[name] = description
        return _Namespace(self, name)

    def _register(self, namespace: str, fn: Callable, description: str):
        sig = inspect.signature(fn)
        params = [
            {
                "name": pname,
                "annotation": str(p.annotation),
                "default": None if p.default is inspect.Parameter.empty else p.default,
            }
            for pname, p in sig.parameters.items()
            if pname != "session"
        ]
        qualified = f"{namespace}.{fn.__name__}"
        self._actions[qualified] = {
            "fn":          fn,
            "description": description,
            "params":      params,
            "namespace":   namespace,
        }

    # ── Dispatch ──────────────────────────────────────────────────────────

    async def call(self, action_name: str, session, **kwargs) -> ActionResult:
        """
        Call a registered action by qualified ("ns.name") or short name.

        Short names are resolved by searching all namespaces; if ambiguous
        an error is returned.
        """
        entry = self._actions.get(action_name)
        if entry is None:
            matches = [k for k in self._actions if k.endswith(f".{action_name}")]
            if len(matches) == 1:
                entry = self._actions[matches[0]]
            elif len(matches) > 1:
                return ActionResult(
                    None, error=f"Ambiguous action {action_name!r}, matches: {matches}"
                )
            else:
                return ActionResult(None, error=f"Unknown action: {action_name!r}")
        try:
            value = await entry["fn"](session, **kwargs)
            return ActionResult(value)
        except Exception:
            import traceback
            return ActionResult(None, error=traceback.format_exc())

    # ── Schema export ─────────────────────────────────────────────────────

    def schemas(self, depth: int = -1) -> list[dict]:
        """
        Return the action registry at varying detail levels.

        depth=0  — namespace names + descriptions only (~minimal tokens)
        depth=1  — namespaces with action name + description (no params)
        depth=-1 — full schemas with parameter details (default)
        """
        ns_groups: dict[str, list[tuple[str, dict]]] = {}
        for qname, entry in self._actions.items():
            ns = entry["namespace"]
            ns_groups.setdefault(ns, []).append((qname, entry))

        result = []
        for ns_name in sorted(ns_groups):
            ns_desc = self._namespaces.get(ns_name, "")

            if depth == 0:
                result.append({
                    "namespace":    ns_name,
                    "description":  ns_desc,
                    "action_count": len(ns_groups[ns_name]),
                })
            elif depth == 1:
                actions = [
                    {"name": qname, "description": e["description"]}
                    for qname, e in ns_groups[ns_name]
                ]
                result.append({
                    "namespace":   ns_name,
                    "description": ns_desc,
                    "actions":     actions,
                })
            else:
                actions = [
                    {
                        "name":        qname,
                        "description": e["description"],
                        "parameters":  e["params"],
                    }
                    for qname, e in ns_groups[ns_name]
                ]
                result.append({
                    "namespace":   ns_name,
                    "description": ns_desc,
                    "actions":     actions,
                })

        return result

    # ── Introspection ─────────────────────────────────────────────────────

    @property
    def names(self) -> list[str]:
        """All qualified action names, sorted."""
        return sorted(self._actions.keys())

    @property
    def namespace_names(self) -> list[str]:
        return sorted(self._namespaces.keys())

    def actions_in(self, namespace: str) -> list[str]:
        """Return qualified action names within a namespace."""
        prefix = namespace + "."
        return sorted(k for k in self._actions if k.startswith(prefix))


# ── Module-level singleton ────────────────────────────────────────────────
# All action modules import this instance so they register into one registry.

controller = SlicerController()
