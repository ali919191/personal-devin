"""Planning module public surface.

Only one public entry point is intentionally exported.
"""

from app.planning.planner import build_execution_plan

__all__ = ["build_execution_plan"]
