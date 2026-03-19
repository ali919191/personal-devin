"""Deterministic callable sandbox for the execution layer."""

from __future__ import annotations

import builtins
import os
import threading
from copy import deepcopy
from typing import Any, Callable

SAFE_BUILTINS = {
    "len": len,
    "range": range,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "sorted": sorted,
    "str": str,
    "Exception": Exception,
    "RuntimeError": RuntimeError,
    "AssertionError": AssertionError,
    "ImportError": ImportError,
    "NameError": NameError,
}

ALLOWED_MODULES = {"math", "json"}
_BUILTINS_LOCK = threading.RLock()


class ExecutionSandbox:
    """
    ExecutionSandbox

    This is a CONTROLLED EXECUTION LAYER, not a security sandbox.

    Guarantees:
    - Restricts builtins to a safe subset
    - Restricts imports via allowlist
    - Prevents accidental global leakage
    - Ensures deterministic execution

    Non-guarantees:
    - Does NOT provide OS-level isolation
    - Does NOT prevent malicious Python escape techniques
    - Does NOT protect against low-level exploits

    Design Intent:
    - Enforce predictable, auditable execution
    - Serve as a foundation for policy + observability layers

    Future extensions (Agent 30+):
    - Execution policies
    - Audit logging
    - Time/resource limits
    """

    def execute(
        self,
        handler: Callable[[Any], Any],
        task: Any,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute *handler* deterministically and return a structured result."""
        with _BUILTINS_LOCK:
            isolated_context = deepcopy(context)
            original_builtins = builtins.__dict__.copy()
            original_environ = {key: value for key, value in os.environ.items()}
            original_str = original_builtins["str"]
            safe_builtins = self._build_safe_builtins(
                original_import=original_builtins["__import__"],
            )

            try:
                builtins.__dict__.clear()
                builtins.__dict__.update(safe_builtins)
                result = handler(task)
                return {
                    "success": True,
                    "output": {"result": result, "context": isolated_context},
                    "error": None,
                }
            except Exception as exc:  # noqa: BLE001
                return {
                    "success": False,
                    "output": {"context": isolated_context},
                    "error": original_str(exc),
                }
            finally:
                builtins.__dict__.clear()
                builtins.__dict__.update(original_builtins)
                os.environ.clear()
                os.environ.update(original_environ)

    def _build_safe_builtins(self, original_import: Callable[..., Any]) -> dict[str, Any]:
        safe_builtins = SAFE_BUILTINS.copy()

        def safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name not in ALLOWED_MODULES:
                raise ImportError(f"Module '{name}' is not allowed")
            return original_import(name, *args, **kwargs)

        safe_builtins["__import__"] = safe_import
        return safe_builtins
