from abc import ABC, abstractmethod
from typing import Any, Dict


class ToolResult:
    def __init__(self, success: bool, output: Any = None, error: str = None):
        self.success = success
        self.output = output
        self.error = error


class Tool(ABC):
    name: str

    @abstractmethod
    def execute(self, input: Dict[str, Any], context: Dict[str, Any]) -> ToolResult:
        pass
