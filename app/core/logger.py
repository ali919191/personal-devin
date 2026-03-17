"""Structured JSON logger for the system."""

import json
import sys
from datetime import datetime
from typing import Any, Optional
from datetime import UTC
from datetime import UTC, datetime

class StructuredLogger:
    """Central structured logger with JSON output."""

    def __init__(self, name: str) -> None:
        """Initialize logger with module name."""
        self.name = name

    def _format_log(
        self,
        level: str,
        action: str,
        data: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> str:
        """Format log as JSON."""
        log_entry = {
                "timestamp": datetime.now(UTC).isoformat(),
            "module": self.name,
            "level": level,
            "action": action,
        }
        if data:
            log_entry["data"] = data
        if error:
            log_entry["error"] = error
        return json.dumps(log_entry)

    def debug(self, action: str, data: Optional[dict[str, Any]] = None) -> None:
        """Log debug message."""
        print(self._format_log("DEBUG", action, data), file=sys.stdout)

    def info(self, action: str, data: Optional[dict[str, Any]] = None) -> None:
        """Log info message."""
        print(self._format_log("INFO", action, data), file=sys.stdout)

    def warning(self, action: str, data: Optional[dict[str, Any]] = None) -> None:
        """Log warning message."""
        print(self._format_log("WARNING", action, data), file=sys.stderr)

    def error(self, action: str, error: str, data: Optional[dict[str, Any]] = None) -> None:
        """Log error message."""
        print(self._format_log("ERROR", action, data, error), file=sys.stderr)

    def critical(
        self, action: str, error: str, data: Optional[dict[str, Any]] = None
    ) -> None:
        """Log critical message."""
        print(self._format_log("CRITICAL", action, data, error), file=sys.stderr)


def get_logger(name: str) -> StructuredLogger:
    """Get a logger instance."""
    return StructuredLogger(name)
