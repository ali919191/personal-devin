"""Deterministic callable sandbox for the execution layer."""

from __future__ import annotations

import builtins
import os
from copy import deepcopy
from types import FunctionType, MethodType, ModuleType
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


class ExecutionSandbox:
    """Executes task handlers with restricted builtins and imports."""

    def execute(
        self,
        handler: Callable[[Any], Any],
        task: Any,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute *handler* deterministically and return a structured result."""
        isolated_context = deepcopy(context)
        original_builtins = builtins.__dict__.copy()
        original_environ = dict(os.environ)
        original_str = original_builtins["str"]
        safe_builtins = self._build_safe_builtins(original_import=original_builtins["__import__"])
        isolated_handler = self._build_isolated_handler(
            handler=handler,
            safe_builtins=safe_builtins,
            context=isolated_context,
        )

        try:
            builtins.__dict__.clear()
            builtins.__dict__.update(safe_builtins)
            result = isolated_handler(task)
            return {
                "success": True,
                "output": {"result": result},
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "output": {},
                "error": original_str(exc),
            }
        finally:
            builtins.__dict__.clear()
            builtins.__dict__.update(original_builtins)
            os.environ.clear()
            os.environ.update(original_environ)

    def _build_safe_builtins(self, original_import: Callable[..., Any]) -> dict[str, Any]:
        safe_builtins = dict(SAFE_BUILTINS)

        def safe_import(name: str, *args: Any, **kwargs: Any) -> ModuleType:
            if name not in ALLOWED_MODULES:
                raise ImportError(f"Module '{name}' is not allowed")
            return original_import(name, *args, **kwargs)

        safe_builtins["__import__"] = safe_import
        return safe_builtins

    def _build_isolated_handler(
        self,
        handler: Callable[[Any], Any],
        safe_builtins: dict[str, Any],
        context: dict[str, Any],
    ) -> Callable[[Any], Any]:
        if isinstance(handler, MethodType):
            isolated_function = self._clone_function(
                handler.__func__,
                safe_builtins=safe_builtins,
                context=context,
            )
            return MethodType(isolated_function, handler.__self__)

        if isinstance(handler, FunctionType):
            return self._clone_function(
                handler,
                safe_builtins=safe_builtins,
                context=context,
            )

        return handler

    def _clone_function(
        self,
        handler: FunctionType,
        safe_builtins: dict[str, Any],
        context: dict[str, Any],
    ) -> FunctionType:
        isolated_globals = self._build_isolated_globals(handler, safe_builtins, context)
        cloned = FunctionType(
            handler.__code__,
            isolated_globals,
            name=handler.__name__,
            argdefs=handler.__defaults__,
            closure=handler.__closure__,
        )
        cloned.__kwdefaults__ = deepcopy(handler.__kwdefaults__)
        cloned.__annotations__ = dict(handler.__annotations__)
        return cloned

    def _build_isolated_globals(
        self,
        handler: FunctionType,
        safe_builtins: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        isolated_globals: dict[str, Any] = {
            "__builtins__": safe_builtins,
            "__name__": handler.__globals__.get("__name__", "__sandbox__"),
            "__package__": handler.__globals__.get("__package__"),
            "__doc__": handler.__globals__.get("__doc__"),
            "__sandbox_context__": context,
        }

        for name, value in handler.__globals__.items():
            if name in isolated_globals or name == "__builtins__":
                continue
            if isinstance(value, ModuleType):
                module_name = getattr(value, "__name__", "")
                if module_name.split(".", 1)[0] in ALLOWED_MODULES:
                    isolated_globals[name] = value
                continue
            isolated_globals[name] = value

        return isolated_globals
